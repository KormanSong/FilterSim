# Third-Party Licenses

MFClab uses the following open-source libraries:

| Library | License | URL |
|---------|---------|-----|
| PySide6 | LGPL v3 | https://www.qt.io/licensing |
| NumPy | BSD 3-Clause | https://numpy.org/doc/stable/license.html |
| SciPy | BSD 3-Clause | https://scipy.org/scipylib/license.html |
| pandas | BSD 3-Clause | https://pandas.pydata.org/pandas-docs/stable/getting_started/overview.html#license |
| PyQtGraph | MIT | https://github.com/pyqtgraph/pyqtgraph/blob/master/LICENSE.txt |
| PyInstaller | GPL v2 (bootloader: custom) | https://pyinstaller.org/en/stable/license.html |

## Notes

- **PySide6** is used under the LGPL v3 license. MFClab dynamically links to PySide6/Qt
  and does not modify its source code.
- **PyInstaller** is a build-time dependency only. The PyInstaller bootloader is distributed
  under a custom license that permits bundling without imposing GPL on the application.
- All other libraries are distributed under permissive BSD/MIT licenses.
