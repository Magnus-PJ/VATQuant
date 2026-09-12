import sys
import slicer

names = list(slicer.app.moduleManager().factoryManager().registeredModuleNames())
print("HAS_VATQUANT", "VATQuant" in names)
print("ATTR", hasattr(slicer.modules, "vatquant"))
m = slicer.util.getModule("VATQuant")
print("GET_MODULE", m is not None)
if hasattr(slicer.modules, "vatquant"):
    w = slicer.modules.vatquant.widgetRepresentation()
    print("WIDGET", w is not None)
else:
    print("WIDGET", False)
    # show nearby names for debugging
    print("SAMPLE", [n for n in names if n.lower().startswith("v")][:20])
sys.exit(0 if "VATQuant" in names else 2)
