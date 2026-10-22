"""OCR adapter with word boxes and confidence. Tesseract is optional; EasyOCR fallback."""
def run_ocr(image, languages="eng"):
    results=[]
    try:
        import pytesseract
        from pytesseract import Output
        data=pytesseract.image_to_data(image, lang=languages, output_type=Output.DICT)
        for i,word in enumerate(data.get("text",[])):
            word=str(word).strip()
            try: conf=float(data["conf"][i])
            except (ValueError,TypeError): conf=-1
            if not word or conf<0: continue
            x,y,w,h=[int(data[k][i]) for k in ("left","top","width","height")]
            results.append({"text":word,"confidence":max(0,min(1,conf/100)),
                            "bbox":{"x1":x,"y1":y,"x2":x+w,"y2":y+h}})
        if results: return results
    except Exception:
        pass
    try:
        import easyocr
        langs=["en"] + (["hi"] if "hin" in languages else [])
        reader=easyocr.Reader(langs,gpu=False,verbose=False)
        import numpy as np
        for box,text,conf in reader.readtext(np.array(image)):
            xs=[p[0] for p in box]; ys=[p[1] for p in box]
            results.append({"text":text,"confidence":float(conf),
                "bbox":{"x1":int(min(xs)),"y1":int(min(ys)),"x2":int(max(xs)),"y2":int(max(ys))}})
    except Exception as e:
        raise RuntimeError("OCR unavailable. Install EasyOCR with 'python -m pip install -r requirements-easyocr.txt'. First run may download model weights. Details: "+str(e))
    return results

def ocr_text(words):
    """Reconstruct approximate lines from word bounding boxes instead of flattening the page."""
    if not words:
        return ""
    ordered=sorted(words,key=lambda w:(w.get("bbox",{}).get("y1",0),w.get("bbox",{}).get("x1",0)))
    lines=[]
    for word in ordered:
        box=word.get("bbox",{})
        y=(box.get("y1",0)+box.get("y2",0))/2
        if not lines or abs(y-lines[-1]["y"])>max(10,(box.get("y2",0)-box.get("y1",0))*0.7):
            lines.append({"y":y,"words":[word]})
        else:
            lines[-1]["words"].append(word)
            n=len(lines[-1]["words"])
            lines[-1]["y"]=(lines[-1]["y"]*(n-1)+y)/n
    return "\n".join(" ".join(str(w.get("text","")) for w in sorted(line["words"],key=lambda w:w.get("bbox",{}).get("x1",0))) for line in lines)
