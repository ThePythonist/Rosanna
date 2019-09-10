from engine import xpaths as real
import sys

xpaths = {}
for key in real:
    xpaths[key] = real[key]

src = None
with open("engine.py", "r") as read:
    src = read.read()


for key in xpaths:
    marker = len(src.split("class AsyncCommand")[0])
    fixable = src[marker:]
    header = src[:marker]
    src = header+fixable.replace("\""+xpaths[key]+"\"", "xpaths[\"%s\"]"%key)

while True:
    marker = len(src.split("class AsyncCommand")[0])

    fixable = src[marker:]
    problem = None
    if "\"//" in fixable:
        problem = len(fixable.split("\"//")[0])+marker
    elif "\"./" in fixable:
        problem = len(fixable.split("\"./")[0])+marker
    else:
        break
    xpath = src[problem:].split("\"")[1]

    print("XPATH: "+xpath+"\n\n")

    contextSize = 500
    context1 = src[problem-contextSize:problem+1]
    context2 = src[problem+len(xpath)+1:problem+len(xpath)+contextSize+1]

    print("Context:\n"+context1, end="")
    print(xpath, file=sys.stderr, end="")
    print(context2)
    print("\n\n")

    label = input("Enter label: ")
    while label in xpaths:
        label = input("Nope taken: ")

    xpaths[label] = xpath
    src = src.replace("\""+xpath+"\"", "xpaths[\"%s\"]"%label)

    xpathString = "xpaths = {"
    i = 0
    for key in xpaths:
        xpathString += "%s\"%s\": \"%s\"," % ("\n          " if i > 0 else "", key, xpaths[key])
        i += 1
    xpathString = xpathString[:-1]+"}"

    incidence = len(src.split("xpaths = {")[0])
    currentXpathsString = src[incidence:].split("}")[0]+"}"

    src = src.replace(currentXpathsString, xpathString)
    
    for i in range(10):
        print("\n")

with open("cleaned.py", "w") as write:
    write.write(src)

print("DONE\n\n")
