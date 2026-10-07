# -*- coding: utf-8 -*-
"""
SELECT LINKED ELEMENT BY ID
============================
Allows the user to select an element inside a Revit linked model
by entering its Element ID — no graphical picking required.

Revit 2024 | pyRevit | No external dependencies
"""

__title__   = "Select\nLinked\nElement"
__doc__     = (
    "Select an element inside a Revit linked model by typing its Element ID.\n\n"
    "1. Choose a loaded linked model from the dropdown.\n"
    "2. Enter the Element ID from that linked model.\n"
    "3. Click SELECT — the element is highlighted in the host view."
)
__author__  = "pyRevit Tool"

import os
import sys
import clr

# ── .NET / WPF references ────────────────────────────────────────────────────
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")
clr.AddReference("System.Xml")

import System
from System import Int64
from System.Collections.Generic import List
from System.Windows import (
    Window, MessageBox, MessageBoxButton, MessageBoxImage, Visibility
)
from System.Windows.Markup import XamlReader
from System.Windows.Controls import ComboBoxItem
from System.Windows.Media import SolidColorBrush, Color
from System.Windows.Input import Key

# ── Revit API ────────────────────────────────────────────────────────────────
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    RevitLinkInstance,
    ElementId,
    Reference,
    Options,
    ViewDetailLevel,
    FamilySymbol,
)

# ── Revit context (injected by pyRevit) ──────────────────────────────────────
uidoc = __revit__.ActiveUIDocument
doc   = uidoc.Document


# ═══════════════════════════════════════════════════════════════════════════════
# LINK UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def get_loaded_link_instances(document):
    """
    Return a list of RevitLinkInstance objects whose linked document is loaded.
    Unloaded links (GetLinkDocument() returns None) are excluded.
    """
    instances = []
    collector = FilteredElementCollector(document).OfClass(RevitLinkInstance)
    for inst in collector:
        if inst.GetLinkDocument() is not None:
            instances.append(inst)
    return instances


def get_link_display_names(link_instances):
    """
    Build display names for the link dropdown.
    Duplicate file names get an '— Instance N' suffix so the user
    can distinguish between multiple placements of the same RVT file.

    Returns: list of (display_name: str, link_instance: RevitLinkInstance)
    """
    # Collect base names (file basename or fallback to element Name)
    base_names = []
    for inst in link_instances:
        linked_doc = inst.GetLinkDocument()
        if linked_doc and linked_doc.PathName:
            base = os.path.basename(linked_doc.PathName)
        else:
            base = inst.Name or "Unknown Link"
        base_names.append(base)

    # Count how many times each base name appears
    name_count = {}
    for n in base_names:
        name_count[n] = name_count.get(n, 0) + 1

    # Assign instance numbers where needed
    seen = {}
    result = []
    for i, inst in enumerate(link_instances):
        base = base_names[i]
        if name_count[base] > 1:
            seen[base] = seen.get(base, 0) + 1
            display = u"{} \u2014 Instance {}  [ID: {}]".format(base, seen[base], inst.Id.Value)
        else:
            display = u"{}  [ID: {}]".format(base, inst.Id.Value)
        result.append((display, inst))

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# ELEMENT ID PARSING  (Revit 2024: 64-bit ElementId)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_element_id(text):
    """
    Parse user-entered text as a Revit 2024 64-bit ElementId.

    Revit 2024 uses System.Int64 for ElementId values.
    Using plain int() / Int32 is NOT reliable for large IDs.

    Returns: (ElementId, None)  on success
             (None, error_str)  on failure
    """
    if not text or not text.strip():
        return None, "Please enter an Element ID."
    try:
        # Explicit Int64.Parse — correct for Revit 2024
        value = Int64.Parse(text.strip())
        return ElementId(value), None
    except Exception:
        return None, (
            "Invalid Element ID.\n\n"
            "Please enter a valid numeric Element ID (e.g. 123456789)."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# LINKED ELEMENT ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

def get_linked_element(link_instance, element_id):
    """
    Retrieve the element from the linked document.

    Returns: (element, None)      on success
             (None, error_str)    on failure
    """
    try:
        linked_doc = link_instance.GetLinkDocument()
        if linked_doc is None:
            name = link_instance.Name or "selected link"
            return None, (
                "{} is currently unloaded.\n"
                "Reload the link and try again.".format(name)
            )
        elem = linked_doc.GetElement(element_id)
        if elem is None:
            return None, (
                "Element ID {} was not found\n"
                "in the selected linked model.".format(element_id.Value)
            )
        return elem, None
    except Exception as ex:
        return None, "Error accessing the linked document:\n{}".format(str(ex))


def get_element_info(element, linked_doc):
    """
    Build a human-readable info string about the linked element.
    Shown in the dialog as a confirmation before the window closes.
    """
    try:
        cat      = element.Category
        cat_name = cat.Name if cat else "(no category)"

        family_name = ""
        type_name   = ""
        try:
            elem_type = linked_doc.GetElement(element.GetTypeId())
            if elem_type is not None:
                if isinstance(elem_type, FamilySymbol):
                    family_name = elem_type.FamilyName
                    type_name   = elem_type.Name
                else:
                    type_name = elem_type.Name
        except Exception:
            pass

        lines = [u"\u2713  Element found", u""]
        lines.append(u"Category : {}".format(cat_name))
        if family_name:
            lines.append(u"Family   : {}".format(family_name))
        if type_name:
            lines.append(u"Type     : {}".format(type_name))
        lines.append(u"ID       : {}".format(element.Id.Value))
        return u"\n".join(lines)
    except Exception:
        return u"\u2713  Element found  (ID: {})".format(element.Id.Value)


# ═══════════════════════════════════════════════════════════════════════════════
# LINKED ELEMENT REFERENCE
# ═══════════════════════════════════════════════════════════════════════════════

def create_linked_element_reference(link_instance, linked_elem):
    """
    Create a host-document Reference that points to an element inside a
    linked model.  This is the reference needed by Selection.SetReferences().

    Strategy
    --------
    Primary (cleanest):
        Reference(linked_elem).CreateLinkReference(link_instance)

        This is the officially documented Revit API method for wrapping a
        linked-element reference into a host-document reference.
        Available in Revit 2023+ (confirmed for Revit 2024).

    Fallback (geometry-based):
        Obtain a geometry Reference from the linked element, convert it to
        a stable string, prepend the link-instance UniqueId, and
        ParseFromStableRepresentation.

        Used for element types where the primary constructor fails
        (e.g. some view-specific annotation elements).

    Returns: (Reference, None)      on success
             (None, error_str)      on failure
    """
    # ── Primary: Reference(element).CreateLinkReference(linkInstance) ──────
    try:
        inner_ref = Reference(linked_elem)
        linked_ref = inner_ref.CreateLinkReference(link_instance)
        if linked_ref is not None:
            return linked_ref, None
    except Exception:
        pass

    # ── Fallback: stable-representation approach ────────────────────────────
    try:
        linked_doc = link_instance.GetLinkDocument()

        opt = Options()
        opt.ComputeReferences    = True
        opt.IncludeNonVisibleObjects = True
        opt.DetailLevel          = ViewDetailLevel.Medium

        geom_elem = linked_elem.get_Geometry(opt)
        if geom_elem is not None:
            for geom_obj in geom_elem:
                try:
                    inner_ref = geom_obj.GetReference()
                except Exception:
                    continue
                if inner_ref is None:
                    continue
                try:
                    # Stable rep of the geometry ref within the linked doc
                    inner_stable = inner_ref.ConvertToStableRepresentation(linked_doc)
                    # Prefix with the link instance UniqueId marker
                    combined = "{}:0:RVTLINK:{}".format(
                        link_instance.UniqueId, inner_stable
                    )
                    host_ref = Reference.ParseFromStableRepresentation(doc, combined)
                    if host_ref is not None:
                        return host_ref, None
                except Exception:
                    continue
    except Exception:
        pass

    # ── Nothing worked ──────────────────────────────────────────────────────
    return None, (
        "The element exists, but Revit does not allow\n"
        "this element type to be selected as a linked element\n"
        "through the current API.\n\n"
        "This may happen with certain annotation or view-specific elements."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SELECTION ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def select_linked_element(link_instance, element_id):
    """
    Full workflow: find the element → build the host reference → select it.

    Returns: (success: bool, elem_info: str or None, error_msg: str or None)
    """
    # Step 1 — find element in linked doc
    linked_elem, err = get_linked_element(link_instance, element_id)
    if err:
        return False, None, err

    linked_doc = link_instance.GetLinkDocument()
    elem_info  = get_element_info(linked_elem, linked_doc)

    # Step 2 — create a host-document Reference pointing to the linked element
    host_ref, err = create_linked_element_reference(link_instance, linked_elem)
    if err:
        return False, elem_info, err

    # Step 3 — apply the selection (no transaction required)
    try:
        ref_list = List[Reference]()
        ref_list.Add(host_ref)
        uidoc.Selection.SetReferences(ref_list)
        return True, elem_info, None
    except Exception as ex:
        return False, elem_info, (
            "Element found but could not be selected in the UI.\n\n"
            "Revit error: {}".format(str(ex))
        )


# ═══════════════════════════════════════════════════════════════════════════════
# WPF DIALOG  (XAML template)
# ═══════════════════════════════════════════════════════════════════════════════

_XAML = u"""
<Window
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    Title="Select Linked Element"
    Width="330"
    SizeToContent="Height"
    WindowStartupLocation="CenterScreen"
    ResizeMode="NoResize"
    Background="#F5F0E8"
    FontFamily="Segoe UI">

    <Window.Resources>
        <!-- Button style -->
        <Style x:Key="PrimaryBtn" TargetType="Button">
            <Setter Property="Background"   Value="#E07856"/>
            <Setter Property="Foreground"   Value="#F5F0E8"/>
            <Setter Property="BorderBrush"  Value="#4C2335"/>
            <Setter Property="Height"       Value="32"/>
            <Setter Property="FontSize"     Value="12"/>
            <Setter Property="FontWeight"   Value="Bold"/>
            <Setter Property="Cursor"       Value="Hand"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="Button">
                        <Border Background="{TemplateBinding Background}"
                                BorderBrush="{TemplateBinding BorderBrush}"
                                BorderThickness="1"
                                CornerRadius="3">
                            <ContentPresenter HorizontalAlignment="Center"
                                              VerticalAlignment="Center"/>
                        </Border>
                        <ControlTemplate.Triggers>
                            <Trigger Property="IsMouseOver" Value="True">
                                <Setter Property="Background" Value="#CF6543"/>
                            </Trigger>
                            <Trigger Property="IsPressed" Value="True">
                                <Setter Property="Background" Value="#B35538"/>
                            </Trigger>
                        </ControlTemplate.Triggers>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>

        <Style x:Key="SecondaryBtn" TargetType="Button">
            <Setter Property="Background"   Value="#F5F0E8"/>
            <Setter Property="Foreground"   Value="#4C2335"/>
            <Setter Property="BorderBrush"  Value="#4C2335"/>
            <Setter Property="Height"       Value="30"/>
            <Setter Property="FontSize"     Value="11"/>
            <Setter Property="Cursor"       Value="Hand"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="Button">
                        <Border Background="{TemplateBinding Background}"
                                BorderBrush="{TemplateBinding BorderBrush}"
                                BorderThickness="1"
                                CornerRadius="3">
                            <ContentPresenter HorizontalAlignment="Center"
                                              VerticalAlignment="Center"/>
                        </Border>
                        <ControlTemplate.Triggers>
                            <Trigger Property="IsMouseOver" Value="True">
                                <Setter Property="Background" Value="#E8E0D5"/>
                            </Trigger>
                        </ControlTemplate.Triggers>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>
    </Window.Resources>

    <StackPanel Margin="20,18,20,20">

        <!-- ── Title ── -->
        <TextBlock
            Text="SELECT LINKED ELEMENT"
            FontSize="13"
            FontWeight="Bold"
            Foreground="#4C2335"
            HorizontalAlignment="Center"
            Margin="0,0,0,4"/>

        <TextBlock
            Text="by Element ID"
            FontSize="10"
            Foreground="#E07856"
            HorizontalAlignment="Center"
            Margin="0,0,0,14"/>

        <!-- ── Divider ── -->
        <Rectangle Height="1" Fill="#4C2335" Opacity="0.3" Margin="0,0,0,16"/>

        <!-- ── LINKED MODEL ── -->
        <Grid Margin="0,0,0,5">
            <Grid.ColumnDefinitions>
                <ColumnDefinition Width="*"/>
                <ColumnDefinition Width="Auto"/>
                <ColumnDefinition Width="140"/>
            </Grid.ColumnDefinitions>
            <TextBlock
                Grid.Column="0"
                Text="LINKED MODEL"
                FontSize="9.5"
                FontWeight="Bold"
                Foreground="#4C2335"
                VerticalAlignment="Bottom"/>
            <TextBlock
                Grid.Column="1"
                Text="Search: "
                FontSize="9.5"
                Foreground="#4C2335"
                VerticalAlignment="Bottom"
                Margin="0,0,4,1"/>
            <TextBox
                x:Name="TxtSearchLinks"
                Grid.Column="2"
                Height="22"
                FontSize="11"
                Padding="4,2"
                Background="#FFFFFF"
                Foreground="#3B332E"
                CaretBrush="#4C2335"
                BorderBrush="#4C2335"
                BorderThickness="1"
                VerticalAlignment="Bottom"/>
        </Grid>

        <ComboBox
            x:Name="CmbLinks"
            Height="30"
            FontSize="12"
            Margin="0,0,0,16"
            Background="#FFFFFF"
            Foreground="#3B332E"
            BorderBrush="#4C2335"
            Padding="6,4"/>

        <!-- ── ELEMENT ID ── -->
        <TextBlock
            Text="ELEMENT ID"
            FontSize="9.5"
            FontWeight="Bold"
            Foreground="#4C2335"
            Margin="0,0,0,5"/>

        <TextBox
            x:Name="TxtElementId"
            Height="30"
            FontSize="13"
            Padding="8,5"
            Background="#FFFFFF"
            Foreground="#3B332E"
            CaretBrush="#4C2335"
            BorderBrush="#4C2335"
            BorderThickness="1"
            Margin="0,0,0,4"/>

        <TextBlock
            Text="Enter the numeric ID from the linked model."
            FontSize="9"
            Foreground="#3B332E"
            Margin="2,0,0,12"/>

        <!-- ── Status / Info area ── -->
        <Border x:Name="StatusBorder"
                Background="#FFFFFF"
                BorderBrush="#E07856"
                BorderThickness="1"
                CornerRadius="3"
                Padding="10,8"
                Margin="0,0,0,14"
                Visibility="Collapsed">
            <TextBlock
                x:Name="TxtStatus"
                FontSize="10.5"
                Foreground="#4C2335"
                TextWrapping="Wrap"
                FontFamily="Consolas"/>
        </Border>

        <!-- ── Divider ── -->
        <Rectangle Height="1" Fill="#4C2335" Opacity="0.3" Margin="0,0,0,14"/>

        <!-- ── Buttons ── -->
        <Button x:Name="BtnSelect"
                Content="SELECT"
                Style="{StaticResource PrimaryBtn}"
                Margin="0,0,0,8"/>

        <Button x:Name="BtnCancel"
                Content="CANCEL"
                Style="{StaticResource SecondaryBtn}"/>

        <!-- ── Footer ── -->
        <TextBlock HorizontalAlignment="Center" Margin="0,14,0,-6" FontSize="9">
            <Hyperlink x:Name="LnkLinkedIn" NavigateUri="https://www.linkedin.com/in/hazem-sakr/" Foreground="#4C2335" TextDecorations="None">
                <Run Text="by " Foreground="#999088"/>
                <Run Text="Hazem Sakr" FontWeight="Bold"/>
            </Hyperlink>
        </TextBlock>

    </StackPanel>
</Window>
"""


class SelectLinkedElementDialog(object):
    """
    WPF dialog for the Select Linked Element tool.
    Loaded from an inline XAML string — no external XAML file required.
    """

    _COLOR_GREEN = Color.FromRgb(0x4C, 0x23, 0x35)   # success (Deep Plum)
    _COLOR_RED   = Color.FromRgb(0xE0, 0x78, 0x56)   # error (Warm Terracotta)

    def __init__(self, link_items):
        """
        link_items : list of (display_name: str, RevitLinkInstance) tuples
        """
        self.link_items = link_items
        self.completed  = False   # True when selection succeeded

        # Parse XAML and get the Window object
        self._window = XamlReader.Parse(_XAML)

        # Locate named controls
        self._cmb_links     = self._window.FindName("CmbLinks")
        self._txt_search    = self._window.FindName("TxtSearchLinks")
        self._txt_id        = self._window.FindName("TxtElementId")
        self._txt_status    = self._window.FindName("TxtStatus")
        self._status_border = self._window.FindName("StatusBorder")
        self._btn_select    = self._window.FindName("BtnSelect")
        self._btn_cancel    = self._window.FindName("BtnCancel")

        self.filtered_links = []
        self._populate_dropdown("")
        self._wire_events()

    # ── Initialisation helpers ────────────────────────────────────────────────

    def _populate_dropdown(self, search_text):
        """Fill the ComboBox with loaded link names, filtered by search_text."""
        self._cmb_links.Items.Clear()
        self.filtered_links = []
        search_lower = search_text.lower()
        
        for display_name, inst in self.link_items:
            match_name = search_lower in display_name.lower()
            match_id   = search_lower in str(inst.Id.Value)
            
            if not search_lower or match_name or match_id:
                self.filtered_links.append((display_name, inst))
                self._cmb_links.Items.Add(display_name)
                
        if self.filtered_links:
            self._cmb_links.SelectedIndex = 0

    def _wire_events(self):
        """Attach event handlers."""
        self._btn_select.Click += self._on_select_clicked
        self._btn_cancel.Click += self._on_cancel_clicked
        self._txt_id.KeyDown   += self._on_id_key_down
        self._txt_search.TextChanged += self._on_search_changed
        
        lnk = self._window.FindName("LnkLinkedIn")
        if lnk:
            lnk.RequestNavigate += self._on_navigate

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_navigate(self, sender, e):
        import System.Diagnostics
        System.Diagnostics.Process.Start(e.Uri.AbsoluteUri)
        e.Handled = True

    def _on_search_changed(self, sender, e):
        """Filter the ComboBox items based on the search text."""
        self._populate_dropdown(self._txt_search.Text)

    def _on_id_key_down(self, sender, e):
        """Press Enter in the ID field → trigger SELECT."""
        if e.Key in (Key.Return, Key.Enter):
            self._on_select_clicked(sender, e)

    def _on_cancel_clicked(self, sender, e):
        self._window.Close()

    def _on_select_clicked(self, sender, e):
        """Validate inputs, perform selection, update UI."""
        # ── Validate: link chosen ─────────────────────────────────────────
        idx = self._cmb_links.SelectedIndex
        if idx < 0 or idx >= len(self.filtered_links):
            self._show_status("Please select a linked model.", error=True)
            return
        _display, link_instance = self.filtered_links[idx]

        # ── Validate: element ID ──────────────────────────────────────────
        element_id, err = parse_element_id(self._txt_id.Text)
        if err:
            self._show_status(err, error=True)
            return

        # ── Perform selection ─────────────────────────────────────────────
        success, elem_info, err = select_linked_element(link_instance, element_id)

        if elem_info:
            # Always show element info when the element was found
            self._show_status(elem_info, error=False)

        if err:
            # Show error in a message box (keeps the dialog open so user can retry)
            MessageBox.Show(
                err,
                "Selection Error",
                MessageBoxButton.OK,
                MessageBoxImage.Warning
            )
            return

        if success:
            # Close the dialog — element is now selected in Revit
            self.completed = True
            self._window.Close()

    # ── Status display ────────────────────────────────────────────────────────

    def _show_status(self, text, error=False):
        """Show or update the status/info panel."""
        color = self._COLOR_RED if error else self._COLOR_GREEN
        self._txt_status.Foreground    = SolidColorBrush(color)
        self._txt_status.Text          = text
        self._status_border.Visibility = Visibility.Visible

    # ── Entry point ───────────────────────────────────────────────────────────

    def show(self):
        """Show the dialog modally. Returns True if selection was made."""
        self._window.ShowDialog()
        return self.completed


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # ── Guard: must have an active document ──────────────────────────────────
    if doc is None:
        MessageBox.Show(
            "No active Revit document found.\nPlease open a project and try again.",
            "No Document",
            MessageBoxButton.OK,
            MessageBoxImage.Warning
        )
        return

    # ── Collect loaded links ──────────────────────────────────────────────────
    loaded_links = get_loaded_link_instances(doc)

    if not loaded_links:
        MessageBox.Show(
            "No loaded Revit links were found\nin the current project.\n\n"
            "Load at least one Revit link and try again.",
            "No Loaded Links",
            MessageBoxButton.OK,
            MessageBoxImage.Information
        )
        return

    # ── Build display names (handles duplicate file names) ───────────────────
    link_items = get_link_display_names(loaded_links)

    # ── Show dialog ───────────────────────────────────────────────────────────
    dlg = SelectLinkedElementDialog(link_items)
    dlg.show()


# pyRevit calls the script directly — run main()
main()
