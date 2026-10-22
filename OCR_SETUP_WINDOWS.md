# OCR setup on Windows

DocGuard's PDF rendering works independently from OCR. The app can display the upload even when OCR is not installed.

## Option A: Install Tesseract (recommended on Windows)
1. Install the Windows Tesseract OCR application from its official UB Mannheim distribution.
2. During setup, select English language data. Select Hindi language data too if you need Hindi OCR.
3. Ensure the Tesseract install folder is on PATH. A common location is `C:\\Program Files\\Tesseract-OCR`.
4. Restart VS Code after installation.
5. In the activated `.venv` terminal, check:
   ```powershell
   tesseract --version
   tesseract --list-langs
   ```
   `eng` should appear. `hin` is needed for Hindi.
6. Run:
   ```powershell
   python -m pip install pytesseract
   python -m streamlit run app.py
   ```

If `tesseract` is installed but not on PATH, add the install folder to PATH or set this near the top of `ocr.py` before calling OCR:
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
```

## Option B: EasyOCR fallback
From the activated `.venv` terminal:
```powershell
python -m pip install easyocr
```
This can download large PyTorch dependencies and may take time on Windows. Tesseract is usually the simpler starting option.

## Test the app
```powershell
python -m pytest -q
python -m streamlit run app.py
```

OCR uses the selected document's first PDF page in the current prototype.
