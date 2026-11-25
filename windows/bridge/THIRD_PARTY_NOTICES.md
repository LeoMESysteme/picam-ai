# Hinweise zu Fremdbestandteilen (Windows-App GSVmulti-Brücke)

## Qt und Qt for Python (PySide6, Shiboken6)

Die Brücke bündelt Qt 6, die Python-Bindings PySide6 und deren
Shiboken6-Laufzeit aus der Qt for Python Community Edition (The Qt Company
und Mitwirkende). Für die mitgelieferten Qt-Bestandteile wird
GNU LGPL Version 3 verwendet.

- [LGPL-3.0-Lizenztext](https://www.gnu.org/licenses/lgpl-3.0.html)
- [Qt-Lizenzen und Hinweise zu Drittbestandteilen](https://doc.qt.io/qt-6/licensing.html)
- [Lizenzhinweise zu Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html)
- Quellcode bei Qt für [Qt 6](https://download.qt.io/archive/qt/) und
  [Qt for Python](https://code.qt.io/cgit/pyside/pyside-setup.git/)

## Fluent UI System Icons

* Herkunft: npm-Paket `@fluentui/svg-icons`, Version 1.1.344
  (Repository https://github.com/microsoft/fluentui-system-icons)
* Verwendung: ausgewählte SVG-Symbole (Regular 20/16, Filled 16), unverändert
  eingebettet in `src/dispread_bridge_app/ui/icons.py`
* Lizenz: MIT

```
MIT License

Copyright (c) 2020 Microsoft Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
