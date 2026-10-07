# Select Linked Element (pyRevit)

![Revit 2024](https://img.shields.io/badge/Revit-2024-0696D7?style=flat-square&logo=autodesk)
![pyRevit](https://img.shields.io/badge/pyRevit-4.8+-red?style=flat-square)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)

A powerful, lightweight pyRevit extension that completely bypasses tedious graphical clicking when dealing with dense linked models. Select any element inside a Revit link instantly by entering its Element ID.

---

## 🚀 Features

*   **Instant Selection**: Bypasses the need to graphically locate and tab-select elements in a 3D view.
*   **Built-in Search**: Quickly filter through your loaded links by name or by the Link's Element ID.
*   **Revit 2024 Ready**: Fully supports the new 64-bit Element IDs and utilizes the modern `SetReferences` API to natively select linked geometry in the host view.
*   **Beautiful UI**: Custom, responsive WPF dialog that seamlessly matches modern Revit aesthetics.

## 📦 Installation

1. Make sure you have [pyRevit](https://github.com/eirannejad/pyRevit) installed.
2. Download or clone this repository.
3. Copy the `SelectLinkedElement.extension` folder to your pyRevit extensions directory. By default, this is:
   `%APPDATA%\pyRevit\Extensions\`
4. Open Revit, go to the **pyRevit** tab, and click **Reload**.
5. The tool will appear in the new **SelectLinkedElement** tab on your ribbon!

## 💡 How to Use

1. Click the **Select Linked Element** button.
2. Select your target **Linked Model** from the dropdown (use the search bar to filter if you have many links).
3. Paste or type the **Element ID** of the target element from the linked model.
4. Hit **Enter** or click **Select**.
5. Revit will instantly select and highlight the linked element in your active view!

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
Created by [Hazem Sakr](https://www.linkedin.com/in/hazem-sakr/)
