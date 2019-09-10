from rosanna.engine import Rosanna
from rosanna.emoji import emoji
from selenium import webdriver

rosanna = Rosanna()

qrCode = rosanna.showQRCode()

rosanna.waitForConnection()

oldPrint = print
def print(x, *args, **kwargs):
    try:
        oldPrint(x, *args, **kwargs)
    except UnicodeEncodeError:
        oldPrint(str(x).encode("utf-8"), *args, **kwargs)

print("Connected")

rosanna.start()

counter = 0

def onReceivedRecentContacts(contacts):
    print("Received %i recent contacts" % len(contacts))
    for i in contacts:
        print(i)
    print("-------------------------")

def onReceivedRecentMessages(messages):
    print("Received %i recent messages" % len(messages))
    for i in messages:
        print(i.sender)
        print(i.timestamp)
        print(i.text)
        print(i.attachment)
        if i.attachment is not None:
            global counter
            i.attachment.save("atts/%i" %counter)
            print("Saved to %i" %counter)
            counter += 1
        print(i.additional)
        print(i.incoming)
        print("\n")
    

def onReceivedRecentMedia(messages):
    print("Received %i media" % len(messages))
    onReceivedRecentMessages(messages)

def onReceivedRecentLinks(messages):
    print("Received %i links" % len(messages))
    onReceivedRecentMessages(messages)

def onReceivedRecentDocs(messages):
    print("Received %i docs" % len(messages))
    onReceivedRecentMessages(messages)

def onReceivedContactDetails(contact):
    print("Received contact details")
    for i in contact.getFieldNames():
        print(i + " " + str(contact.getField(i)))
    if contact.getField("Profile Picture") is not None:
        global counter
        contact.getField("Profile Picture").save("atts/%i" %counter)
        print("Saved to %i" %counter)
        counter += 1
    print("-------------------------")

#Test sending
rosanna.sendMessage("Test", "Hello", callback=lambda : print("Sent message"))
rosanna.sendPhotoOrVideo("Test", "Unicorn.jpeg", callback=lambda : print("Sent photo"))
rosanna.sendContact("Test", "Lollums", callback=lambda : print("Sent contact"))
rosanna.sendDocument("Test", "rosanna/engine.py", callback=lambda : print("Sent document"))

#Test receiving
rosanna.getRecentContacts(30, onReceivedRecentContacts)
rosanna.getRecentMessages("Test", 40, onReceivedRecentMessages)
rosanna.getRecentMedia("Lollums", 30, onReceivedRecentMedia)
rosanna.getRecentLinks("JuJuBee", 30, onReceivedRecentLinks)
rosanna.getRecentDocuments("Lollums", 30, onReceivedRecentDocs)

#Test getting contact details
trials = ["JuJuBee",
          "Lollums",
          "literally anything else",
          "Party 9th Feb",
          "Bri "+emoji("heavy black heart")+emoji("face with three hearts")]
for name in trials:
    rosanna.getContactDetails(name, callback=onReceivedContactDetails)

rosanna.queueStop()
