from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from PIL import Image
from threading import Thread, Lock
from pygame.locals import *
from bs4 import BeautifulSoup
from io import BytesIO
from selenium.webdriver.common.keys import Keys
import time
import base64
import io
import pygame
import warnings
import os
import inspect
import shutil
import re
import traceback
import html

warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

class Queue:
    def __init__(self):
        self.queue = []

    def push(self, val):
        self.queue.append(val)

    def pop(self):
        val = self.queue[0]
        del self.queue[0]
        return val

    def empty(self):
        return len(self.queue) == 0

class Attachment:
    def __init__(self, type, fileExtension, data, saveable=True):
        self.type = type
        self.fileExtension = fileExtension
        self.data = data
        self.saveable = saveable
        
    def save(self, path, addExtension=True):
        if self.canSave():
            with open(path + ("."+self.fileExtension if addExtension else ""), "wb") as write:
                write.write(self.data)

    def canSave(self):
        return self.saveable

class ImageAttachment(Attachment):
    def __init__(self, fileExtension, data):
        Attachment.__init__(self, "Image", fileExtension, data)

    def toPILImage(self):
        stream = io.BytesIO(self.data)
        img = Image.open(stream)
        return img

    def show(self):
        self.toPILImage().show()

class GIFAttachment(Attachment):
    def __init__(self, fileExtension, data):
        Attachment.__init__(self, "GIF", fileExtension, data)

class VideoAttachment(Attachment):
    def __init__(self, fileExtension, data):
        Attachment.__init__(self, "Video", fileExtension, data)

class StickerAttachment(ImageAttachment):
    def __init__(self, fileExtension, data):
        Attachment.__init__(self, "Sticker", fileExtension, data)

class DocumentAttachment(Attachment):
    def __init__(self, filename, fileExtension, data):
        Attachment.__init__(self, "Document", fileExtension, data)
        self.filename = filename

class FailedDownloadAttachment(Attachment):
    def __init__(self):
        Attachment.__init__(self, "Failed Download", "", bytes(), saveable=False)

class AudioAttachment(Attachment):
    def __init__(self, fileExtension, data):
        Attachment.__init__(self, "Audio", fileExtension, data)

class AdditionalData:
    def __init__(self, type):
        self.type = type

class LocationData(AdditionalData):
    def __init__(self, latitude, longitude, live):
        AdditionalData.__init__(self, "Location")
        self.latitude = latitude
        self.longitude = longitude
        self.live = live

class ContactData(AdditionalData):
    def __init__(self, info):
        AdditionalData.__init__(self, "Contact")
        self.info = info
        
    def getField(self, key):
        return self.info[key]

    def getFieldNames(self):
        return list(self.info.keys())

    def hasField(self, key):
        return key in self.info

#Behold the mountain of XPATHs
#Abandon hope all ye who dare to climb
xpaths = {"introImage": "//div[@data-asset-intro-image='true']",
          "searchBar": "//input[@title='Search or start new chat']",
          "messageBar": "//div[text()='Type a message']/following-sibling::div",
          "sendButton": "//span[@data-icon='send']/..",
          "contactSearchResults": "//div[@id='pane-side']/descendant::div[contains(@style,'height: 49px; width: 49px')]/../.././../..",
          "contactSearchResultName": "./div/div/div/div[position()=1]/descendant::span[@title!='']",
          "currentContactSpan": "//div[@id='main']/header/div[position()=2]/div/div/span",
          "qrCode": "//img[@alt='Scan me!']",
          "messageText": "./descendant::span[contains(@class,'selectable-text invisible-space copyable-text')]",
          "onlyEmojiMessageText": "./div/div/div/div/div[contains(@class,'selectable-text invisible-space copyable-text')]/span",
          "messageImage": "./div/div/div/div/img[not(@draggable)]",
          "messageSticker": "./div/div/div/div/img[@draggable='false']",
          "messageImageDownloadButton": "./descendant::span[@data-icon='media-download']",
          "messageMetadata": "./descendant::div[@data-pre-plain-text!='']",
          "photosAndVideosInput": "//li[position()=1]/button/input",
          "attachContactButton": "//li[position()=4]/button",
          "documentInput": "//li[position()=3]/button/input",
          "attachButton": "//div[@title='Attach']",
          "attachButtonActiveWrapper": "./..[contains(@class, ' ')]",
          "sendMediaButton": "//span[@data-icon='send-light']/..",
          "photoVideoCaptionBar": "//span[text()='Add a caption…']/../descendant::div[contains(@class,'copyable-text selectable-text')]",
          "messageVideoPip": "./descendant::span[@data-icon='video-pip']/..",
          "videoWrapper": "//video[@autoplay]/../../../..",
          "messageGIF": "./descendant::video",
          "messageDocument": "./descendant::a[@href='#']/div/..",
          "messageAudio": "./descendant::audio",
          "messageLocation": "./descendant::a[contains(@href,'maps.google')]",
          "messageLiveLocation": "./descendant::div/span/img[contains(@src,'maps.google')]",
          "messageImageLoading": "./descendant::span[@data-icon='media-disabled']",
          "messageContact": "./div/div/div[@role='button']",
          "messageContactWindow": "//div[text()='View contact']/ancestor::div[@data-animate-modal-popup='true']",
          "messageContactWindowClose": "./descendant::span[@data-icon='x-light']/ancestor::button",
          "messageContactData": "./div/div/div/div/div/div/div[position()=2]/div",
          "sendContactWindow": "//div[text()='Send contacts']/ancestor::div[@data-animate-modal-popup='true']",
          "searchContactInput": "./descendant::input[@title='Search…']",
          "sendContactSearchMatch": "./descendant::span[@title!='']",
          "sendContactButton": "./descendant::div[@role='button']",
          "sendContactConfirmWindow": "//span[contains(@title, 'Send 1 contact to ')]/ancestor::div[@data-animate-modal-popup='true']",
          "titleBar": "//div[@data-asset-chat-background='true']/../header/div[position()=2]/div/div/span",
          "mediaLinksDocsButton": "//span[text()='Media, Links and Docs']",
          "mediaPreviewDiv": "//div[@data-list-scroll-container='true']/span/div/div/div/div/div[position()=2]",
          "linksButton": "//button[@title='Links']",
          "docsButton": "//button[@title='Docs']",
          "linkDiv": "./span/div/div/div/div[not(@tabindex)]|./span/div/div/div/div[@tabindex]/div[not(@tabindex)]",
          "listContainer": "//div[@data-list-scroll-container='true']",
          "docDiv": "./span/div/div/div/div",
          "contactDetailsWrapper": "//div[@id='app']/div/div/div[position()=2]/div[position()=3]",
          "contactData": "./descendant::span[contains(@class,'selectable-text invisible-space copyable-text')]",
          "contactInfoHeader": "./descendant::div[contains(text(),'info')]",
          "mutedContact": "./span/div/span/div/div/div/div[position()=3]/div/div/div[position()=2]/div/div[contains(@class, ' ')]",
          "groupName": "./descendant::div[contains(@class,'copyable-text selectable-text')]",
          "revealMoreMembers": "./descendant::span[@data-icon='down']",
          "participant": "./descendant::div[contains(@style,'z-index')]",
          "admin": "./descendant::div[text()='Group admin']",
          "listLoading": "./descendant::*[local-name() = 'svg']/*[local-name()='circle']",
          "myIcon": "//header/div/div[contains(@style,'height: 40px; width: 40px;')]",
          "sidePane": "//div[@id='pane-side']",
          "translatedDiv": "./descendant::div[contains(@style,'translateY(%ipx)')]",
          "classDiv": "./div[@class]",
          "starredMessagesButton": "./descendant::div[@role='button']/descendant::span[text()='Starred Messages']/../../..",
          "starredContainer": "//div[contains(@class,'copyable-area')]/div/div",
          "starDiv": "./span/div",
          "starPlatform": "./descendant::span[@data-icon='chevron-right-alt']/..",
          "velocityDiv": "//div[contains(@style,'background-color')]",
          "starBackButton": "./descendant::span[contains(@data-icon,'back')]/..",
          "closeButton": "./span/div/span/div/header/div/div/button",
          "myContactDetailsWrapper": "//div[@id='app']/div/div/div/div",
          "myNameAndDesc": "./descendant::div[contains(@class,'copyable-text selectable-text')]",
          "myProfilePic": "./span/div/div/div/div/div/div/div/div/div/img",
          "myContactBackButton": "./span/div/div/header/div/div/button",
          "profileText": "//div[@id='app']/div/div/div/div/span/div/div/header/div/div[text()='Profile']",
          "zoomOutButton": "//span[@data-icon='minus']/..",
          "zoomInButton": "//span[@data-icon='plus']/..",
          "checkmark": "//span[contains(@data-icon,'checkmark')]/..",
          "anyTranslatedDiv": "//div[contains(@style, 'translateY')]",
          "globalTranslatedDiv": "//div[contains(@style, 'translateY(%ipx)')]",
          "messageWindow": "//div[@id='main']/div[position()=3]/div/div",
          "mediaWrapper": "//div[@id='app']/div/span/div/div/div[position()=2]/div[position()=2]",
          "documentPopup": "//div[@id='app']/div/span/div/div/span",
          "video": "//video",
          "parent": "./..",
          "editButton": "./descendant::div[contains(@class,'copyable-text selectable-text')]/../../span/div",
          "inputDescendant": "./descendant::input",
          "profilePicImage": "./span/div/span/div/div/div/div/div/div/img[not(contains(@src,'dyn'))]",
          "defaultProfilePic": "./span/div/span/div/div/div/div/div/div/div/span[@data-icon='default-user']",
          "participantCount": "./span/div/span/div/div/div/div[position()=5]/div/div/div/div/span",
          "scrollable": "./span/div/span/div/div",
          "nameNestedSpan": "./div/div/div[position()=2]/div/div/span/span",
          "nameSpan": "./div/div/div[position()=2]/div/div/span[@dir]",
          "bigProfilePicture": "./descendant::div[contains(@style,'width: 200px; height: 200px;')]/img[not(contains(@src,'dyn'))]",
          "defaultGroupIcon": "./descendant::span[@data-icon='default-group']",
          "messageDiv": "./div[last()]/div",
          "previousButton": "./descendant::span[@title='Previous']",
          "linkDocScrollableParent": "./span/div/div/div",
          "documentPlatform": "./div/div/div/div/div",
          "messageIn": "./descendant::div[contains(@class, 'message-in')]",
          "messageOut": "./descendant::div[contains(@class, 'message-out')]",
          "starred": "./descendant::span[contains(@data-icon,'star')]",
          "contactName": "./descendant::span[@dir='auto']",
          "companies": "./div/div/div/div/div/div/div/div[position()=2]/div[position()=2]/div",
          "fakeProfilePic": "./descendant::img[contains(@src,'dyn')]",
          "realProfilePic": "./descendant::img[not(contains(@src,'dyn'))]",
          "contactDataValue": "./descendant::*[contains(@class,'selectable-text invisible-space copyable-text')]",
          "contactDataKey": "./div/div/div[position()=2]",
          "imageDescendant": "./descendant::img",
          "videoDescendant": "./descendant::video[not(@loop)]",
          "gifDescendant": "./descendant::video[@loop]",
          "unstarButton": "//span[@data-icon='unstar-btn']",
          "blobResult": "./*[@id='blobResult']",
          "starMessageButton": "//div[contains(@style,'transform-origin')]/ul/li/div[contains(@title,'tar message')]",
          "replyButton": "//div[contains(@style,'transform-origin')]/ul/li/div[@title='Reply']",
          "deleteMessageButton": "//div[contains(@style,'transform-origin')]/ul/li/div[@title='Delete message']",
          "contextArrow": "./descendant::span[@data-icon='down-context']/..",
          "messageSmallerDiv": "./div",
          "replyingBar": "//div[@id='main']/div[contains(@style, 'height')]",
          "replyingTo": "./div/div/div/div/div/div[@role='button']",
          "returnToBottomButton": "//div[@role='button'][@style='transform: scaleX(1) scaleY(1); opacity: 1;']",
          "deleteMessageButtons": "./div/div/div/div",
          "deleteMessageLimitedButtons": "./div/div/div[@role='button']",
          "deletePopup": "//div[@data-animate-modal-popup='true']",
          "goToMessageButton": "//div[@role='button'][@title='Go to message']",
          "previewContainer": "//div[@data-list-scroll-container='true']",
          "starMediaButton": "//div[@role='button'][contains(@title, 'tar message')]",
          "mediaSender": "./../div/div/div[position()=2]/div/span",
          "mediaCloseButton": "./../descendant::div[@title='Close']",
          "muteButton": "//li/div[@role='button'][contains(@title,'ute')]"}

class AsyncCommand(Thread):
    def __init__(self, func, rosanna):
        Thread.__init__(self)
        self.func = func
        self.rosanna = rosanna

    def run(self):
        self.func(self.rosanna)

class Command:
    def __init__(self, args, callback=lambda x, y: None):
        self.args = args
        self.callback = callback

    def executeAsync(self, rosanna):
        comm = AsyncCommand(self.execute, rosanna)
        comm.start()

class SearchContactCommand(Command):
    def execute(self, rosanna):
        searchBar = rosanna.findElement(xpaths["searchBar"])
        rosanna.clear(searchBar)
        rosanna.sendKeys(searchBar, self.args["contactName"])
        container = rosanna.findElement(xpaths["sidePane"])
        rosanna.findElement(xpaths["translatedDiv"] % 0)
        results = []
        offset = 1+self.args["startPos"]
        finished = False
        while not finished:
            worked = False
            while not worked:
                worked = True
                try:
                    rosanna.waitForLoading(base=container)
                    result = rosanna.findElement(xpaths["translatedDiv"] % (offset*72), base=container, timeout=0.01)
                    if result is None:
                        finished = True
                    else:
                        rosanna.runScript("arguments[0].scrollIntoView()", result)
                        children = result.find_elements_by_xpath(xpaths["classDiv"])
                        if len(children) > 0:
                            finished = True
                        else:
                            offset += 1
                            contactInteractable = ContactInteractable(rosanna, result)
                            name = contactInteractable.read()
                            if self.args["bouncer"] is not None:
                                self.args["bouncer"].enqueue(name, contactInteractable, offset-1)
                                while self.args["bouncer"].holding:
                                    pass
                                if self.args["bouncer"].interrupted:
                                    finished = True
                            results.append(name)
                            if len(results) >= self.args["count"] and self.args["count"] >= 0:
                                finished = True
                except StaleElementReferenceException:
                    worked = False
        if self.args["bouncer"] is not None:
            self.args["bouncer"].done = True
        self.callback(results, rosanna)
        
class SelectContactCommand(Command):
    def execute(self, rosanna):
        if rosanna.currentContact != self.args["contactName"]:
            match = None
            bouncer = Bouncer()
            argsToUse = {}
            for key in self.args:
                argsToUse[key] = self.args[key]
            argsToUse["bouncer"] = bouncer
            argsToUse["count"] = -1
            argsToUse["startPos"] = 0
            searchCommand = SearchContactCommand(argsToUse)
            searchCommand.executeAsync(rosanna)
            while bouncer.getNext():
                name, contactInteractable = bouncer.next
                if name == self.args["contactName"]:
                    match = contactInteractable
                    bouncer.interrupt()
                bouncer.release()
            if match is None:
                print("Can't find contact")
            match.select()
            rosanna.currentContact = self.args["contactName"]
            self.callback(match, rosanna)
        else:
            self.callback(None, rosanna)        

class GetRecentStarredCommand(Command):
    def execute(self, rosanna):
        selectContactCommand = SelectContactCommand(self.args, self.onSelectedContact)
        selectContactCommand.execute(rosanna)

    def onSelectedContact(self, match, rosanna):
        titleBar = rosanna.findElement(xpaths["titleBar"])
        rosanna.click(titleBar)

        wrapper = rosanna.findElement(xpaths["contactDetailsWrapper"])

        starredMessagesButton = rosanna.findElement(xpaths["starredMessagesButton"], base=wrapper)
        rosanna.click(starredMessagesButton)

        messages = []
        container = rosanna.findElement(xpaths["starredContainer"])
        rosanna.waitForLoading(base=container)
        starDivs = []
        startTime = time.time()
        strikes = 0
        for i in range(len(self.args["startPos"])):
            divs = container.find_elements_by_xpath(xpaths["starDiv"])
            if len(divs) == 0:
                break
            div = divs[0]
            rosanna.runScript("arguments[0].scrollIntoView();", div)
            rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0]);", div)
        while (self.args["timeout"] < 0 or time.time()-startTime < self.args["timeout"]) and (len(starDivs) < self.args["count"] or self.args["count"] < 0) and strikes < 3:
            rosanna.runScript("arguments[0].scrollTop=arguments[0].scrollHeight;", container)
            starDivs = container.find_elements_by_xpath(xpaths["starDiv"])
            loadingEls = container.find_elements_by_xpath(xpaths["listLoading"])
            if len(loadingEls) == 0:
                strikes += 1
            else:
                strikes = 0
            startTime = time.time()
        while len(messages) < self.args["count"] or self.args["count"] < 0:
            divs = container.find_elements_by_xpath(xpaths["starDiv"])
            if len(divs) == 0:
                break
            div = divs[0]
            rosanna.runScript("arguments[0].scrollIntoView();", div)
            platform = rosanna.findElement(xpaths["starPlatform"], base=div)
            rosanna.click(platform)
            styled = rosanna.findElement(xpaths["velocityDiv"])
            messageDiv = rosanna.findElement(xpaths["parent"], base=styled)
            rosanna.runScript("arguments[0].removeAttribute('style')", styled)

            messageInteractable = MessageInteractable(rosanna, messageDiv)
            message = messageInteractable.read(args=self.args)
            if message is not None:
                messages.append(message)
                if self.args["bouncer"] is not None:
                    self.args["bouncer"].enqueue(message, messageInteractable, len(messages)+self.args["startPos"])
                    while self.args["bouncer"].holding:
                        pass
                    if self.args["bouncer"].interrupted:
                        break
            rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0]);", div)

        if self.args["bouncer"] is not None:
            self.args["bouncer"].done = True

        backButton = rosanna.findElement(xpaths["starBackButton"], base=wrapper)
        rosanna.click(backButton)
        
        closeButton = rosanna.findElement(xpaths["closeButton"], base=wrapper)
        rosanna.click(closeButton)

        buttons = [None]
        while len(buttons) > 0:
            buttons = wrapper.find_elements_by_xpath(xpaths["closeButton"])
        
        self.callback(messages, rosanna)

class GetMyContactDetailsCommand(Command):
    def execute(self, rosanna):
        myIcon = rosanna.findElement(xpaths["myIcon"])
        rosanna.click(myIcon)

        profilePic = None

        info = {}
        
        wrapper = rosanna.findElement(xpaths["myContactDetailsWrapper"])

        nameEl, descEl = rosanna.findElements(xpaths["myNameAndDesc"], base=wrapper)
        info["Name"] = rosanna.getText(nameEl)
        info["Description"] = rosanna.getText(descEl)
        
        ppEls = wrapper.find_elements_by_xpath(xpaths["myProfilePic"])
        if len(ppEls) > 0:
            b64 = ppEls[0].get_attribute("src")
            if "base64" not in b64:
                b64 = rosanna.parseBlob(b64, ppEls[0])
            meta, b64 = b64.split(";base64,")
            ext = meta.split("/")[1]
            if ";" in ext:
                ext = ext.split(";")[0]
            imageBytes = base64.b64decode(b64)
            profilePic = ImageAttachment(ext, imageBytes)

        info["Profile Picture"] = profilePic

        contact = ContactData(info)

        backButton = rosanna.findElement(xpaths["myContactBackButton"], base=wrapper)
        rosanna.click(backButton)

        wrappers = [None]
        while len(wrappers) > 0:
            wrappers = rosanna.driver.find_elements_by_xpath(xpaths["profileText"])
        
        self.callback(contact, rosanna)

class SetMyNameCommand(Command):
    def execute(self, rosanna):
        myIcon = rosanna.findElement(xpaths["myIcon"])
        rosanna.click(myIcon)

        profilePic = None

        info = {}
        
        wrapper = rosanna.findElement(xpaths["myContactDetailsWrapper"])

        editButton = rosanna.findElement(xpaths["editButton"], base=wrapper)
        rosanna.click(editButton)
        
        nameEl = rosanna.findElement(xpaths["groupName"], base=wrapper)
        rosanna.clear(nameEl)
        rosanna.sendKeys(nameEl, self.args["name"])
        rosanna.sendKeys(nameEl, Keys.RETURN)

        backButton = rosanna.findElement(xpaths["myContactBackButton"], base=wrapper)
        rosanna.click(backButton)

        wrappers = [None]
        while len(wrappers) > 0:
            wrappers = rosanna.driver.find_elements_by_xpath(xpaths["profileText"])
        
        self.callback(rosanna)

class SetMyDescriptionCommand(Command):
    def execute(self, rosanna):
        myIcon = rosanna.findElement(xpaths["myIcon"])
        rosanna.click(myIcon)

        profilePic = None

        info = {}
        
        wrapper = rosanna.findElement(xpaths["myContactDetailsWrapper"])

        editButton = rosanna.findElements(xpaths["editButton"], base=wrapper)[1]
        rosanna.click(editButton)
        
        descEl = rosanna.findElements(xpaths["groupName"], base=wrapper)[1]
        rosanna.clear(descEl)
        rosanna.sendKeys(descEl, self.args["description"])
        rosanna.sendKeys(descEl, Keys.RETURN)

        backButton = rosanna.findElement(xpaths["myContactBackButton"], base=wrapper)
        rosanna.click(backButton)

        wrappers = [None]
        while len(wrappers) > 0:
            wrappers = rosanna.driver.find_elements_by_xpath(xpaths["profileText"])
        
        self.callback(rosanna)

class SetMyProfilePictureCommand(Command):
    def execute(self, rosanna):
        myIcon = rosanna.findElement(xpaths["myIcon"])
        rosanna.click(myIcon)

        profilePic = None

        info = {}
        
        wrapper = rosanna.findElement(xpaths["myContactDetailsWrapper"])

        imageInput = rosanna.findElement(xpaths["inputDescendant"])
        rosanna.sendKeys(imageInput, self.args["path"])

        zoomOutButton = rosanna.findElement(xpaths["zoomOutButton"])
        zoomInButton = rosanna.findElement(xpaths["zoomInButton"])

        zoomButton = zoomInButton if self.args["zoom"] > 0 else zoomOutButton
        for i in range(abs(self.args["zoom"])):
            rosanna.click(zoomButton)

        confirmButton = rosanna.findElement(xpaths["checkmark"])
        rosanna.click(confirmButton)

        backButton = rosanna.findElement(xpaths["myContactBackButton"], base=wrapper)
        rosanna.click(backButton)

        wrappers = [None]
        while len(wrappers) > 0:
            wrappers = rosanna.driver.find_elements_by_xpath(xpaths["profileText"])
        
        self.callback(rosanna)


class GetContactDetailsCommand(Command):
    def execute(self, rosanna):
        selectContactCommand = SelectContactCommand(self.args, self.onSelectedContact)
        selectContactCommand.execute(rosanna)

    def onSelectedContact(self, match, rosanna):
        info = {}
        name = None
        description = None
        profilePic = None

        ppSrc = None
        
        titleBar = rosanna.findElement(xpaths["titleBar"])
        rosanna.click(titleBar)

        wrapper = rosanna.findElement(xpaths["contactDetailsWrapper"])

        header = rosanna.getText(rosanna.findElement(xpaths["contactInfoHeader"]))
        if header == "Contact info":
            nameSpan, descSpan, numberSpan = rosanna.findElements(xpaths["contactData"], base=wrapper)
            name = rosanna.getText(nameSpan)
            description = rosanna.getText(descSpan)
            info["Number"] = rosanna.getText(numberSpan)

            profilePicEl, matchIndex = rosanna.findFirstElement([xpaths["profilePicImage"],
                                                                 xpaths["defaultProfilePic"]],
                                                                base=wrapper)
            if matchIndex == 0:
                ppSrc = profilePicEl.get_attribute("src")
            
        elif header == "Group info":
            nameDiv = rosanna.findElement(xpaths["groupName"], base=wrapper)
            descSpan = rosanna.findElement(xpaths["contactData"], base=wrapper)
            name = rosanna.getText(nameDiv)
            description = rosanna.getText(descSpan)

            reveals = wrapper.find_elements_by_xpath(xpaths["revealMoreMembers"])
            if len(reveals) > 0:
                rosanna.click(reveals[0])

            partCountSpan = rosanna.findElement(xpaths["participantCount"], base=wrapper)
            partCount = int(rosanna.getText(partCountSpan).split(" ")[0])
            
            participantEls = []
            participants = []
            participantYs = []
            admins = []
            scrollable = rosanna.findElement(xpaths["scrollable"], base=wrapper)
            while len(participants) < partCount:
                worked = False
                while not worked:
                    worked = True
                    try:
                        participantEls = rosanna.findElements(xpaths["participant"], base=wrapper)
                        for participant in participantEls:
                            style = participant.get_attribute("style")
                            y = int(style.split("translateY(")[1].split("px)")[0])
                            if y not in participantYs:
                                participantYs.append(y)
                                nameSpan, matchIndex = rosanna.findFirstElement([xpaths["nameNestedSpan"],
                                                                                 xpaths["nameSpan"]],
                                                                                base=participant)
                                participantName = rosanna.getText(nameSpan) 
                                participants.append(participantName)
                                adminEls = participant.find_elements_by_xpath(xpaths["admin"])
                                if len(adminEls) > 0:
                                    admins.append(participantName)
                    except StaleElementReferenceException:
                        worked = False
                rosanna.runScript("arguments[0].scrollTop += 72", scrollable)
            
            info["Participants"] = participants
            info["Administrators"] = admins

            profilePicEl, matchIndex = rosanna.findFirstElement([xpaths["bigProfilePicture"],
                                                                 xpaths["defaultGroupIcon"]],
                                                                base=wrapper)
            if matchIndex == 0:
                ppSrc = profilePicEl.get_attribute("src")

        if ppSrc is not None:
            b64 = ppSrc
            if "base64" not in b64:
                b64 = rosanna.parseBlob(b64, profilePicEl)
            meta, b64 = b64.split(";base64,")
            ext = meta.split("/")[1]
            if ";" in ext:
                ext = ext.split(";")[0]
            imageBytes = base64.b64decode(b64)
            profilePic = ImageAttachment(ext, imageBytes)
                

        info["Name"] = name
        info["Description"] = description
        info["Profile Picture"] = profilePic

        mutedContacts = wrapper.find_elements_by_xpath(xpaths["mutedContact"])
        info["Muted"] = bool(len(mutedContacts))

        contact = ContactData(info)

        closeButton = rosanna.findElement(xpaths["closeButton"], base=wrapper)
        rosanna.click(closeButton)

        buttons = [None]
        while len(buttons) > 0:
            buttons = wrapper.find_elements_by_xpath(xpaths["closeButton"])
        
        self.callback(contact, rosanna)
        
        

class SendMessageCommand(Command):
    def execute(self, rosanna):
        selectContactCommand = SelectContactCommand(self.args, self.onSelectedContact)
        selectContactCommand.execute(rosanna)

    def onSelectedContact(self, match, rosanna):
        messageBar = rosanna.findElement(xpaths["messageBar"])
        rosanna.sendKeys(messageBar, self.args["message"])

        sendButton = rosanna.findElement(xpaths["sendButton"])
        rosanna.click(sendButton)

        sendButtons = [None]
        while len(sendButtons) > 0:
            sendButtons = rosanna.driver.find_elements_by_xpath(xpaths["sendButton"])
        
        self.callback(self.args["message"], rosanna)

class SendPhotoOrVideoCommand(Command):
    def execute(self, rosanna):
        selectContactCommand = SelectContactCommand(self.args, self.onSelectedContact)
        selectContactCommand.execute(rosanna)

    def onSelectedContact(self, match, rosanna):
        attachButton = rosanna.findElement(xpaths["attachButton"])
        rosanna.click(attachButton)

        photoOrVideoInput = rosanna.findElement(xpaths["photosAndVideosInput"])
        rosanna.sendKeys(photoOrVideoInput, self.args["path"])

        captionBar = rosanna.findElement(xpaths["photoVideoCaptionBar"])
        rosanna.sendKeys(captionBar, self.args["caption"])

        sendButton = rosanna.findElement(xpaths["sendMediaButton"])
        rosanna.click(sendButton)

        sendButtons = [None]
        while len(sendButtons) > 0:
            sendButtons = rosanna.driver.find_elements_by_xpath(xpaths["sendMediaButton"])

        attachButtonActiveWrappers = attachButton.find_elements_by_xpath(xpaths["attachButtonActiveWrapper"])
        while len(attachButtonActiveWrappers) > 0:
            attachButton.click()
            attachButtonActiveWrappers = attachButton.find_elements_by_xpath(xpaths["attachButtonActiveWrapper"])

        self.callback(self.args["path"], rosanna)

class SendDocumentCommand(Command):
    def execute(self, rosanna):
        selectContactCommand = SelectContactCommand(self.args, self.onSelectedContact)
        selectContactCommand.execute(rosanna)

    def onSelectedContact(self, match, rosanna):
        attachButton = rosanna.findElement(xpaths["attachButton"])
        rosanna.click(attachButton)

        documentInput = rosanna.findElement(xpaths["documentInput"])
        rosanna.sendKeys(documentInput, self.args["path"])

        sendButton = rosanna.findElement(xpaths["sendMediaButton"])
        rosanna.click(sendButton)

        sendButtons = [None]
        while len(sendButtons) > 0:
            sendButtons = rosanna.driver.find_elements_by_xpath(xpaths["sendMediaButton"])


        attachButtonActiveWrappers = attachButton.find_elements_by_xpath(xpaths["attachButtonActiveWrapper"])
        while len(attachButtonActiveWrappers) > 0:
            attachButton.click()
            attachButtonActiveWrappers = attachButton.find_elements_by_xpath(xpaths["attachButtonActiveWrapper"])

        self.callback(self.args["path"], rosanna)

class SendContactCommand(Command):
    def execute(self, rosanna):
        selectContactCommand = SelectContactCommand(self.args, self.onSelectedContact)
        selectContactCommand.execute(rosanna)

    def onSelectedContact(self, match, rosanna):
        attachButton = rosanna.findElement(xpaths["attachButton"])
        rosanna.click(attachButton)

        attachContactButton = rosanna.findElement(xpaths["attachContactButton"])
        rosanna.click(attachContactButton)

        contactWindow = rosanna.findElement(xpaths["sendContactWindow"])
        contactSearchInput = rosanna.findElement(xpaths["searchContactInput"], base=contactWindow)
        rosanna.sendKeys(contactSearchInput, self.args["contact"])

        match = None
        worked = False
        while not worked:
            worked = True
            try:
                results = rosanna.findElements(xpaths["sendContactSearchMatch"])
                for result in results:
                    text = result.get_attribute("title")
                    if text == self.args["contact"]:
                        match = result
                        break
            except StaleElementReferenceException:
                worked = False
        rosanna.click(match)

        sendButton = rosanna.findElement(xpaths["sendContactButton"], base=contactWindow)
        sendButton.click()
        
        confirmWindow = rosanna.findElement(xpaths["sendContactConfirmWindow"])

        sendButton = rosanna.findElement(xpaths["sendContactButton"], base=confirmWindow)
        sendButton.click()

        windows = [None]
        while len(windows) > 0:
            windows = rosanna.driver.find_elements_by_xpath(xpaths["sendContactConfirmWindow"])

        self.callback(self.args["contact"], rosanna)

class GetRecentContactsCommand(Command):
    def execute(self, rosanna):
        searchBar = rosanna.findElement(xpaths["searchBar"])
        rosanna.clear(searchBar)
        contacts = []
        finished = False
        rosanna.runScript("document.getElementById('pane-side').scrollTop=0;")
        rosanna.findElement(xpaths["anyTranslatedDiv"])
        offset = self.args["startPos"]
        while not finished:
            worked = False
            while not worked:
                try:
                    result = rosanna.findElement(xpaths["globalTranslatedDiv"] % (72*offset), timeout=0.01)
                    if result is None:
                        finished = True
                    else:
                        contactInteractable = ContactInteractable(rosanna, result)
                        name = contactInteractable.read()
                        offset += 1
                        contacts.append(name)
                        if self.args["bouncer"] is not None:
                            self.args["bouncer"].enqueue(name, contactInteractable, offset)
                            while self.args["bouncer"].holding:
                                pass
                            if self.args["bouncer"].interrupted:
                                finished = True
                    worked = True
                except:
                    pass
            
            newHeight = float(rosanna.runScript("return document.getElementById('pane-side').scrollTop = document.getElementById('pane-side').scrollTop+72"))
            if len(contacts) == self.args["count"]:
                finished = True
        if self.args["bouncer"] is not None:
            self.args["bouncer"].done = True
        self.callback(contacts, rosanna)

class Timestamp:
    def __init__(self, hour, minute, year, month, day):
        self.hour = hour
        self.minute = minute
        self.year = year
        self.month = month
        self.day = day

    def __str__(self, american=True):
        return "%s:%s %i/%i/%i" % (str(self.hour).rjust(2, "0"),
                                   str(self.minute).rjust(2, "0"),
                                   self.month if american else self.day,
                                   self.day if american else self.month,
                                   self.year)

class Message:
    def __init__(self, sender, timestamp, text, attachment, additional, incoming, starred, isReply):
        self.sender = sender
        self.timestamp = timestamp
        self.text = text
        self.attachment = attachment
        self.additional = additional
        self.incoming = incoming
        self.starred = starred
        self.isReply = isReply

    def getLinks(self):
        if self.text is None:
            return []
        domainsFile = mimesFile = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))+"\\domains.txt"
        domains = ""
        with open(domainsFile) as read:
            domains = read.read()
        domains = [x for x in domains.split("\n") if x != ""]
        suff = "(%s)" % ")|(".join(domains)
        regex = "(([A-Za-z]+:\\/\\/[A-Za-z0-9-._~:\\/?#[\\]@!\$&'()*+,;=%]+)|((www\\.[A-Za-z0-9][[A-Za-z0-9-._~:\\/?#[\\]@!\\$&'()*+,;=%]*\\.[[A-Za-z0-9-._~:\\/?#[\\]@!\\$&'()*+,;=%]+)|([A-Za-z0-9][A-Za-z0-9-._~:\\/?#[\\]@!\\$&'()*+,;=%]*\\.(" + suff +"))))"
        p = re.compile(regex)
        matches = p.findall(self.text)
        links = list(i[0] for i in matches)
        return list(set(links))

class GetRecentMessagesCommand(Command):
    def execute(self, rosanna):
        self.deletedDivs = self.args["startPos"]
        selectContactCommand = SelectContactCommand(self.args, self.onSelectedContact)
        selectContactCommand.execute(rosanna)
        

    def notifyOfDeletedDiv(self, count=1):
        self.deletedDivs += count

    def onSelectedContact(self, match, rosanna):
        messageDivs = []
        startTime = time.time()
        stopped = False
        window = rosanna.findElement(xpaths["messageWindow"])
        messages = []
        for i in range(self.deletedDivs):
            rosanna.waitForLoading(base=window)
            divs = window.find_elements_by_xpath(xpaths["messageDiv"])
            if len(divs) == 0:
                break
            
            div = divs[-1]
            rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0])", div)
        while len(messages) < self.args["count"] or self.args["count"] < 0:
            rosanna.waitForLoading(base=window)
            divs = window.find_elements_by_xpath(xpaths["messageDiv"])
            if len(divs) == 0:
                break
            
            div = divs[-1]
            messageInteractable = MessageInteractable(rosanna, div)
            message = messageInteractable.read(args=self.args)
            if message is not None:
                messages.append(message)
                if self.args["bouncer"] is not None:
                    self.args["bouncer"].enqueue(message, messageInteractable, self.deletedDivs)
                    while self.args["bouncer"].holding:
                        pass
                    if self.args["bouncer"].interrupted:
                        break
            returnButtons = []
            strikes = 0
            while len(returnButtons) == 0 and strikes < 3:
                returnButtons = rosanna.driver.find_elements_by_xpath(xpaths["returnToBottomButton"])
                strikes += 1
            toDelete = 1
            self.deletedDivs += 1
            if len(returnButtons) > 0:
                rosanna.click(returnButtons[0])
                toDelete = self.deletedDivs
            for i in range(toDelete):
                rosanna.waitForLoading(base=window)
                divs = window.find_elements_by_xpath(xpaths["messageDiv"])
                if len(divs) == 0:
                    break
                
                div = divs[-1]
                
                rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0])", div)
            
        if self.args["bouncer"] is not None:
            self.args["bouncer"].done = True

        if not self.args["fast"]:
            rosanna.driver.refresh()
            rosanna.currentContact = None
            rosanna.waitForConnection()
        self.callback(messages, rosanna)

class StopCommand(Command):
    def execute(self, rosanna):
        rosanna.stop()

class GetRecentMediaLinksDocsCommand(Command):
    def execute(self, rosanna):
        self.position = 0
        self.hasBeenDeletion = False
        selectContactCommand = SelectContactCommand(self.args, self.onSelectedContact)
        selectContactCommand.execute(rosanna)

    def notifyOfDeletion(self):
        self.hasBeenDeletion = True

    def onSelectedContact(self, match, rosanna):
        titleBar = rosanna.findElement(xpaths["titleBar"])
        rosanna.click(titleBar)

        mediaLinksDocsButton = rosanna.findElement(xpaths["mediaLinksDocsButton"])

        rosanna.click(mediaLinksDocsButton)

        messages = []

        if self.args["target"] == "Media":
            firstMediaPreview = rosanna.driver.find_elements_by_xpath(xpaths["mediaPreviewDiv"])
            if len(firstMediaPreview) > 0:
                firstMediaPreview = firstMediaPreview[0]
                wrappers = []
                while len(wrappers) == 0:
                    rosanna.click(firstMediaPreview)
                    wrappers = rosanna.driver.find_elements_by_xpath(xpaths["mediaWrapper"])
                stopped = False
                for i in range(self.args["startPos"]):
                    wrapper = rosanna.findElement(xpaths["mediaWrapper"])
                    previousButton = rosanna.findElement(xpaths["previousButton"], base=wrapper)
                    buttonHolder = rosanna.findElement("..", base=previousButton)
                    bClass = buttonHolder.get_attribute("class")
                    if len(bClass)-len(bClass.replace(" ","")) == 2:
                        stopped = True
                    self.position += 1
                while (len(messages) < self.args["count"] or self.args["count"] < 0) and not stopped:
                    wrapper = rosanna.findElement(xpaths["mediaWrapper"])
                    mediaInteractable = MediaInteractable(rosanna, wrapper)
                    message = mediaInteractable.read(args=self.args)
                    messages.append(message)
                    if self.args["bouncer"] is not None:
                        self.args["bouncer"].enqueue(message, mediaInteractable, self.position)
                        while self.args["bouncer"].holding:
                            pass
                        if self.args["bouncer"].interrupted:
                            break
                    wrapper = rosanna.findElement(xpaths["mediaWrapper"])
                    previousButton = rosanna.findElement(xpaths["previousButton"], base=wrapper)
                    buttonHolder = rosanna.findElement("..", base=previousButton)
                    bClass = buttonHolder.get_attribute("class")
                    if len(bClass)-len(bClass.replace(" ","")) == 2:
                        stopped = True
                    elif not self.hasBeenDeletion:
                        rosanna.click(previousButton)
                        self.position += 1
                    else:
                        self.hasBeenDeletion = False
                if self.args["bouncer"] is not None:
                    self.args["bouncer"].done = True
                closeButton = rosanna.findElement(xpaths["mediaCloseButton"], base=wrapper)
                rosanna.click(closeButton)
        elif self.args["target"] in ["Links", "Documents"]:
            button = None
            if self.args["target"] == "Links":
                button = rosanna.findElement(xpaths["linksButton"])
            else:
                button = rosanna.findElement(xpaths["docsButton"])
            rosanna.click(button)
            container = rosanna.findElement(xpaths["listContainer"])
            rosanna.waitForLoading(base=container)
            for i in range(self.args["startPos"]):
                divs = container.find_elements_by_xpath(xpaths[key])
                if len(divs) == 0:
                    break
                div = divs[0]
                if len(divs) == 1:
                    parent = rosanna.findElement(xpaths["linkDocScrollableParent"], base=container)
                    rosanna.hoverOver(div)
                    rosanna.runScript("arguments[0].scrollTop += 100;", parent)
                rosanna.waitForLoading(base=container)
                rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0]);", div)
            while len(messages) < self.args["count"] or self.args["count"] < 0:
                key = "docDiv"
                if self.args["target"] == "Links":
                    key = "linkDiv"
                divs = container.find_elements_by_xpath(xpaths[key])
                if len(divs) == 0:
                    break
                div = divs[0]
                if len(divs) == 1:
                    parent = rosanna.findElement(xpaths["linkDocScrollableParent"], base=container)
                    rosanna.hoverOver(div)
                    rosanna.runScript("arguments[0].scrollTop += 100;", parent)
                rosanna.waitForLoading(base=container)
                messageDiv = div
                if not self.args["stripped"]:
                    platform = None
                    if self.args["target"] == "Links":
                        platform = div.find_elements_by_xpath(xpaths["messageText"])
                        if len(platform) == 0:
                            break
                        platform = platform[0]
                        rosanna.runScript("arguments[0].innerHTML='Processing...'", platform)
                    else:
                        platform = div.find_elements_by_xpath(xpaths["documentPlatform"])
                        if len(platform) == 0:
                            break
                        platform = platform[0]
                    rosanna.click(platform)
                    styled = rosanna.findElement(xpaths["velocityDiv"])
                    messageDiv = rosanna.findElement(xpaths["parent"], base=styled)
                    rosanna.runScript("arguments[0].removeAttribute('style')", styled)
                    
                messageInteractable = MessageInteractable(rosanna, messageDiv)
                message = messageInteractable.read(args=self.args)
                if message is not None:
                    messages.append(message)
                    if self.args["bouncer"] is not None:
                        self.args["bouncer"].enqueue(message, messageInteractable, len(messages)+self.args["startPos"])
                        while self.args["bouncer"].holding:
                            pass
                        if self.args["bouncer"].interrupted:
                            break
                rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0]);", div)
                    
            if self.args["bouncer"] is not None:
                self.args["bouncer"].done = True

        wrapper = rosanna.findElement(xpaths["contactDetailsWrapper"])
        backButton = rosanna.findElement(xpaths["closeButton"], base=wrapper)
        rosanna.click(backButton)

        closeButton = rosanna.findElement(xpaths["closeButton"], base=wrapper)
        rosanna.click(closeButton)

        buttons = [None]
        while len(buttons) > 0:
            buttons = wrapper.find_elements_by_xpath(xpaths["closeButton"])
        
        self.callback(messages, rosanna)
        
  
class QRWindow(Thread):
    def __init__(self, image):
        Thread.__init__(self)
        self.image = image
        self.stopped = False

    def stop(self):
        self.stopped = True

    def run(self):
        screen = pygame.display.set_mode(self.image.size, 0, 32)
        pygame.display.set_caption("Scan QR Code")
        mode = self.image.mode
        size = self.image.size
        data = self.image.tobytes()

        surface = pygame.image.fromstring(data, size, mode)

        while not self.stopped:
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    self.stop()
            screen.blit(surface, (0, 0))
            pygame.display.update()

def decode(arg):
    if type(arg) == bytes:
        return arg.decode("utf-8")
    return arg

class Rosanna(Thread):
    idCounter = 0
    def __init__(self, driver=None, sessionName="default", tmpDir="tmp"):
        Thread.__init__(self)
        self.id = Rosanna.idCounter
        Rosanna.idCounter += 1
        self.saveSession = sessionName is not None
        self.sessionName = sessionName
        self.tmpDir = tmpDir
        self.currentCommand = None
        if self.tmpDir[-1] in ["\\", "/"]:
            self.tmpDir = self.tmpDir[:-1]
        self.tmpDir = os.path.abspath(self.tmpDir)
        self.downloadsDir = os.path.abspath("%s\\rosanna%i\\downloads" % (self.tmpDir, self.id))
        if os.path.isdir("%s\\rosanna%i" % (self.tmpDir, self.id)):
            self.deleteTempDir()
        if not os.path.isdir(self.downloadsDir):
            os.makedirs(self.downloadsDir)
        if driver is None or driver == "headless":
            options = Options()
            options.headless = driver == "headless"
            profile = webdriver.FirefoxProfile()
            profile.set_preference("browser.download.folderList", 2)
            profile.set_preference("browser.download.manager.showWhenStarting", False)
            profile.set_preference("browser.helperApps.alwaysAsk.force", False)
            profile.set_preference("browser.download.dir", self.downloadsDir)
            mimesFile = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))+"\\mimes.txt"
            mimes = ""
            with open(mimesFile) as read:
                mimes = read.read()
            profile.set_preference("browser.helperApps.neverAsk.saveToDisk", mimes)
            profile.set_preference("pdfjs.disabled", True)
            self.driver = webdriver.Firefox(firefox_profile=profile, options=options)
        else:
            self.driver = driver
        attempts = 0
        while attempts < 10:
            try:
                self.driver.get("https://web.whatsapp.com")
                break
            except WebDriverException:
                attempts += 1
        if attempts >= 10:
            print("Didn't work")
        if self.saveSession:
            if not os.path.exists("saves"):
                os.makedirs("saves")
            try:
                rawSessDat = ""
                with open("saves/%s.sess"%self.sessionName, "r") as read:
                    rawSessDat = read.read()
                sessLines = [x for x in rawSessDat.split("\n") if len(x) > 0]
                for line in sessLines:
                    key, val = line.split(": ")
                    self.runScript("window.localStorage.setItem('%s', '%s')" % (key, val))
                self.driver.refresh()
            except FileNotFoundError:
                pass
        self.queue = Queue()
        self.stopped = False
        self.started = False
        self.currentContact = None
        self.gotQRCode = False
        self.qrCodeWindow = None

    def getStorageItems(self):
        return self.runScript("""var items = {}, ls = window.localStorage;
            for (var i = 0, k; i < ls.length; i++)
                items[k = ls.key(i)] = ls.getItem(k);
            return items;""").items()

    def findElements(self, xpath, base=None, timeout=30):
        if base is None:
            base = self.driver
        startTime = time.time()
        while timeout < 0 or time.time()-startTime < timeout:
            elements = base.find_elements_by_xpath(xpath)
            if len(elements) > 0:
                return elements
        return []

    def findElement(self, xpath, base=None, timeout=30):
        elements = self.findElements(xpath, base=base, timeout=timeout)
        if len(elements) == 0:
            return None
        return elements[0]

    def findFirstElements(self, xpathList, base=None, timeout=30):
        if base is None:
            base = self.driver
        startTime = time.time()
        while timeout < 0 or time.time()-startTime < timeout:
            for i, xpath in enumerate(xpathList):
                elements = base.find_elements_by_xpath(xpath)
                if len(elements) > 0:
                    return elements, i
        return [], -1

    def findFirstElement(self, xpathList, base=None, timeout=30):
        elements, matchIndex = self.findFirstElements(xpathList, base=base, timeout=timeout)
        if len(elements) == 0:
            return None, -1
        return elements[0], matchIndex

    def waitForLoading(self, strikeCount=2, base=None):
        if base is None:
            base = self.driver
        strikes = 0
        loadingEls = [None]
        while strikes < strikeCount:
            if len(loadingEls) > 0:
                strikes = 0
            else:
                strikes += 1
            loadingEls = base.find_elements_by_xpath(xpaths["listLoading"])

    def wrapInTimeout(self, timeout, func, *args):
        startTime = time.time()
        err = None
        while timeout < 0 or time.time()-startTime < timeout:
            try:
                func(*args)
                return None
            except Exception as e:
                err = e
        return err

    def getText(self, element):
        innerHTML = element.get_attribute("innerHTML")
        soup = BeautifulSoup(innerHTML, "html.parser")
        emojiTags = soup.findAll("img")
        for tag in emojiTags:
            b = ""
            if "data-plain-text" in tag.attrs:
                b = tag["data-plain-text"]
            elif "alt" in tag.attrs:
                b = tag["alt"]
            tag.replace_with(b)
        otherTags = soup.findAll()
        for tag in otherTags:
            if "data-app-text-template" in tag.attrs:
                template = tag["data-app-text-template"].replace("${", "{")
                tag.replace_with(template.format(appText=tag.getText()))
            else:
                tag.replace_with(tag.getText())
        text = str(soup)
        unescaped = html.unescape(text)
        return unescaped

    def downloadDocument(self, docEl, timeout=30):
        self.click(docEl)
        popup = self.findElement(xpaths["documentPopup"], timeout=5)
        if popup is None:
            return FailedDownloadAttachment()
        name = ""
        data = bytes()
        file = ""
        downloaded = False
        startTime = time.time()
        while not downloaded and (time.time()-startTime < timeout or timeout < 0):
            try:
                downloads = os.listdir(self.downloadsDir)
                if len(downloads) != 0:
                    startTime = time.time()
                if len(downloads) == 1:
                    name = downloads[0]
                    if len(name) < 5 or name[-5:] != ".part": 
                        file = os.path.abspath("%s\\%s" % (self.downloadsDir, name))
                        with open(file, "rb") as read:
                            data = read.read()
                        if len(data) > 0:
                            downloaded = True
            except PermissionError as e:
                pass
        
        inClear = 0
        while inClear < 100:
            dirs = os.listdir(self.downloadsDir)
            if len(dirs) > 0:
                inClear = 0
                time.sleep(0.1)
            else:
                inClear += 1
            while len(dirs) > 0:
                for j in dirs:
                    try:
                        self.deleteFile(os.path.abspath("%s\\%s" % (self.downloadsDir, j)))
                    except FileNotFoundError:
                        pass
                dirs = os.listdir(self.downloadsDir)
            
        ext = ""    
        if "." in name:
            ext = name.split(".")[-1]
            name = ".".join(name.split(".")[:-1])
        attachment = DocumentAttachment(name, ext, data)
        
        popups = self.driver.find_elements_by_xpath(xpaths["documentPopup"])
        if len(popups) > 0:
            self.runScript("arguments[0].parentNode.removeChild(arguments[0]);", popups[0])
        while len(popups) > 0:
            popups = self.driver.find_elements_by_xpath(xpaths["documentPopup"])
            
        return attachment

    def loadMessageFromDiv(self, div, args):
        self.runScript("arguments[0].scrollIntoView();", div)
        sender = None
        timestamp = None
        text = None
        attachment = None
        additional = None
        incoming = None
        starred = False
        isReply = False

        foundVideo = False

        metaEls = div.find_elements_by_xpath(xpaths["messageMetadata"])
        if len(metaEls) == 0 and "Timestamp" in args["filters"]:
            return None
        elif len(metaEls) > 0 and "No Timestamp" in args["filters"]:
            return None
        messageInEls = div.find_elements_by_xpath(xpaths["messageIn"])
        messageOutEls = div.find_elements_by_xpath(xpaths["messageOut"])

        if len(messageInEls) > 0:
            incoming = True
        elif "Incoming" in args["filters"]:
            return None

        
        if len(messageOutEls) > 0:
            incoming = False
        elif "Outgoing" in args["filters"]:
            return None

        if incoming is None:
            return None            

        textEls = div.find_elements_by_xpath(xpaths["messageText"])
        textEls += div.find_elements_by_xpath(xpaths["onlyEmojiMessageText"])
        if len(textEls) == 0 and "Text" in args["filters"]:
            return None
        elif len(textEls) > 0 and "No Text" in args["filters"]:
            return None
        imgButtonEls = []
        if "Image" not in args["ignoreAttachments"] or "Video" not in args["ignoreAttachments"]:
            imgButtonEls = div.find_elements_by_xpath(xpaths["messageImageDownloadButton"])
        if len(imgButtonEls) > 0:
            self.click(imgButtonEls[0])
            imageLoadingEls = [None]
            while len(imageLoadingEls) > 0:
                imageLoadingEls = div.find_elements_by_xpath(xpaths["messageImageLoading"])
                    
        stickerEls = []
        if "Sticker" not in args["ignoreAttachments"]:
            stickerEls = div.find_elements_by_xpath(xpaths["messageSticker"])
        if len(stickerEls) == 0 and "Sticker" in args["filters"]:
            return None
        elif len(stickerEls) > 0 and "No Sticker" in args["filters"]:
            return None
        imgEls = []
        if "Image" not in args["ignoreAttachments"]:
            imgEls = div.find_elements_by_xpath(xpaths["messageImage"])
        if len(imgEls) == 0 and "Image" in args["filters"]:
            return None
        elif len(imgEls) > 0 and "No Image" in args["filters"]:
            return None
        gifEls = []
        if "GIF" not in args["ignoreAttachments"]:
            gifEls = div.find_elements_by_xpath(xpaths["messageGIF"])
        if len(gifEls) == 0 and "GIF" in args["filters"]:
            return None
        elif len(gifEls) > 0 and "No GIF" in args["filters"]:
            return None
        audioEls = []
        if "Audio" not in args["ignoreAttachments"]:
            audioEls = div.find_elements_by_xpath(xpaths["messageAudio"])
        if len(audioEls) == 0 and "Audio" in args["filters"]:
            return None
        elif len(audioEls) > 0 and "No Audio" in args["filters"]:
            return None
        blobEls = imgEls + gifEls + audioEls + stickerEls

        videoEls = []
        if "Video" not in args["ignoreAttachments"]:
            videoEls = div.find_elements_by_xpath(xpaths["messageVideoPip"])
        if len(videoEls) == 0 and "Video" in args["filters"]:
            return None
        elif len(videoEls) > 0 and "No Video" in args["filters"]:
            return None

        docEls = []
        if "Document" not in args["ignoreAttachments"]:
            docEls = div.find_elements_by_xpath(xpaths["messageDocument"])
        if len(docEls) == 0 and "Document" in args["filters"]:
            return None
        elif len(docEls) > 0 and "No Document" in args["filters"]:
            return None

        locEls = []
        if "Location" not in args["ignoreAdditional"]:
            locEls = div.find_elements_by_xpath(xpaths["messageLocation"])

        liveLocEls = []
        if "Live Location" not in args["ignoreAdditional"] and "Location" not in args["ignoreAdditional"]:
            liveLocEls = div.find_elements_by_xpath(xpaths["messageLiveLocation"])
        if len(liveLocEls) == 0 and "Live Location" in args["filters"]:
            return None
        elif len(liveLocEls) > 0 and "No Live Location" in args["filters"]:
            return None
        if len(locEls + liveLocEls) == 0 and "Location" in args["filters"]:
            return None
        elif len(locEls + liveLocEls) > 0 and "No Location" in args["filters"]:
            return None

        contactEls = []
        if "Contact" not in args["ignoreAdditional"]:
            contactEls = div.find_elements_by_xpath(xpaths["messageContact"])
        if len(contactEls) == 0 and "Contact" in args["filters"]:
            return None
        elif len(contactEls) > 0 and "No Contact" in args["filters"]:
            return None

        starred = len(div.find_elements_by_xpath(xpaths["starred"])) == 1
        if starred and "Unstarred" in args["filters"]:
            return None
        elif not starred and "Starred" in args["filters"]:
            return None

        replies = div.find_elements_by_xpath(xpaths["replyingTo"])
        isReply = len(replies) > 0
        if isReply and "Not Reply" in args["filters"]:
            return None
        elif not isReply and "Reply" in args["filters"]:
            return None

        if not incoming:
            sender = "You"

        if len(metaEls) > 0:
            metadata = metaEls[0].get_attribute("data-pre-plain-text")
            dt = metadata[1:metadata.index("]")]
            time_, date = dt.split(", ")
            hour, minute = time_.split(":")
            month, day, year = date.split("/")
            timestamp = Timestamp(int(hour), int(minute), int(year), int(month), int(day))
            if incoming:
                sender = metadata[metadata.index("]")+2:-2]
        
        if len(textEls) > 0:
            text = self.getText(textEls[0])

        
        if len(blobEls) > 0:
            src = blobEls[0].get_attribute("src")
            b64 = ""
            if "base64," not in src:
                b64 = self.parseBlob(src, blobEls[0])
            else:
                b64 = src
            meta, b64 = b64.split(";base64,")
            ext = meta.split("/")[1]
            if ";" in ext:
                ext = ext.split(";")[0]
            imageBytes = base64.b64decode(b64)
            AttachmentClass = ImageAttachment
            if len(audioEls) > 0:
                AttachmentClass = AudioAttachment
            elif len(gifEls) > 0:
                AttachmentClass = GIFAttachment
            elif len(stickerEls) > 0:
                AttachmentClass = StickerAttachment
            attachment = AttachmentClass(ext, imageBytes)

        
        if len(videoEls) > 0:
            self.click(videoEls[0])
            video = self.findElement(xpaths["video"])
            pauseScript = "arguments[0].pause();"
            self.runScript(pauseScript, video)
            src = video.get_attribute("src")
            b64 = ""
            if "base64," not in src:
                b64 = self.parseBlob(src, div)
            else:
                b64 = src
            videoWrapper = self.findElement(xpaths["videoWrapper"])
            deleteElScript = "arguments[0].parentNode.removeChild(arguments[0]);"
            self.runScript(deleteElScript, videoWrapper)
            meta, b64 = b64.split(";base64,")
            ext = meta.split("/")[1]
            videoBytes = base64.b64decode(b64)
            attachment = VideoAttachment(ext, videoBytes)

        
        if len(docEls) > 0:
            attachment = self.downloadDocument(docEls[0], timeout=args["timeout"])

        
        if len(locEls) > 0:
            href = locEls[0].get_attribute("href")
            lat, long = href.split("?q=")[1].split("&")[0].split("%2C")
            additional = LocationData(float(lat), float(long), False)

        
        if len(liveLocEls) > 0:
            src = liveLocEls[0].get_attribute("src")
            lat, long = src.split("&center=")[1].split("&")[0].split("%2C+")
            additional = LocationData(float(lat), float(long), True)

        
        if len(contactEls) > 0:
            self.click(contactEls[0])
            contactWindow = self.findElement(xpaths["messageContactWindow"])

            info = {}

            info["Name"] = contactWindow.find_element_by_xpath(xpaths["contactName"]).get_attribute("title")
            companies = contactWindow.find_elements_by_xpath(xpaths["companies"])
            if len(companies) > 0:
                info["Company"] = self.getText(companies[0])

            fakeProfilePics = []
            profilePics = []
            if args["loadContactProfilePics"]:
                fakeProfilePics = contactWindow.find_elements_by_xpath(xpaths["fakeProfilePic"])
                profilePics = contactWindow.find_elements_by_xpath(xpaths["realProfilePic"])
            if len(fakeProfilePics) > 0:
                while len(profilePics) == 0:
                    profilePics = contactWindow.find_elements_by_xpath(xpaths["realProfilePic"])
            if len(profilePics) > 0:
                src = profilePics[0].get_attribute("src")
                b64 = self.parseBlob(src, profilePics[0])
                meta, b64 = b64.split(";base64,")
                ext = meta.split("/")[1]
                if ";" in ext:
                    ext = ext.split(";")[0]
                imageBytes = base64.b64decode(b64)
                info["Profile Picture"] = ImageAttachment(ext, imageBytes)

            dataObjects = contactWindow.find_elements_by_xpath(xpaths["messageContactData"])
            for dataObject in dataObjects:
                value = self.getText(dataObject.find_element_by_xpath(xpaths["contactDataValue"]))
                name = self.getText(dataObject.find_element_by_xpath(xpaths["contactDataKey"]))
                info[name] = value

            messageButtons = contactEls[0].find_elements_by_xpath("./../descendant::div[text()='Message']")
            if len(messageButtons) > 0:
                info["On Whatsapp"] = True
            else:
                info["On Whatsapp"] = False

            additional = ContactData(info)

            closeContactButton = self.findElement(xpaths["messageContactWindowClose"])
            self.click(closeContactButton)

            windows = [None]
            while len(windows) > 0:
                windows = self.driver.find_elements_by_xpath(xpaths["messageContactWindow"])
                    
        return Message(sender, timestamp, text, attachment, additional, incoming, starred, isReply)

    def loadMediaFromWrapper(self, wrapper, args):
        loadingEls = [None]
        imgButtonEls = wrapper.find_elements_by_xpath(xpaths["messageImageDownloadButton"])
        if len(imgButtonEls) > 0:
            self.click(imgButtonEls[0])
                
        startTime = time.time()
        while (args["timeout"] < 0 or time.time()-startTime < args["timeout"]) and len(loadingEls) > 0:
            loadingEls = wrapper.find_elements_by_xpath(xpaths["messageImageLoading"])

        imgEls = wrapper.find_elements_by_xpath(xpaths["imageDescendant"])
        if len(imgEls) == 0 and "Image" in args["filters"]:
            return None
        elif len(imgEls) > 0 and "No Image" in args["filters"]:
            return None
        videoEls = wrapper.find_elements_by_xpath(xpaths["videoDescendant"])
        if len(videoEls) == 0 and "Video" in args["filters"]:
            return None
        elif len(videoEls) > 0 and "No Video" in args["filters"]:
            return None
        gifEls = wrapper.find_elements_by_xpath(xpaths["gifDescendant"])
        if len(gifEls) == 0 and "GIF" in args["filters"]:
            return None
        elif len(gifEls) > 0 and "No GIF" in args["filters"]:
            return None
        audioEls = wrapper.find_elements_by_xpath(xpaths["messageAudio"])
        if len(audioEls) == 0 and "Audio" in args["filters"]:
            return None
        elif len(audioEls) > 0 and "No Audio" in args["filters"]:
            return None

        starred = len(self.driver.find_elements_by_xpath(xpaths["unstarButton"])) > 0
        if starred and "Unstarred" in args["filters"]:
            return None
        elif not starred and "Starred" in args["filters"]:
            return None
        captionEls = wrapper.find_elements_by_xpath(xpaths["contactName"])
        if len(captionEls) == 0 and "Text" in args["filters"]:
            return None
        elif len(captionEls) > 0 and "No Text" in args["filters"]:
            return None

        senderSpan = self.findElement(xpaths["mediaSender"], base=wrapper)
        sender = self.getText(senderSpan)

        incoming = sender != "You"
        if incoming and "Outgoing" in args["filters"]:
            return None
        elif not incoming and "Incoming" in args["filters"]:
            return None

        pausable = videoEls + audioEls
        for element in pausable:
            self.runScript("arguments[0].pause();", element)

        blobEls = imgEls + videoEls + gifEls + audioEls
        if len(blobEls) > 0:
            blobEl = blobEls[0]
            src = blobEl.get_attribute("src")
            b64 = ""
            if not "base64" in src:
                b64 = self.parseBlob(src, blobEl)
            else:
                b64 = src
            meta, b64 = b64.split(";base64,")
            ext = meta.split("/")[1]
            if ";" in ext:
                ext = ext.split(";")[0]
            data = base64.b64decode(b64)
            AttachmentClass = ImageAttachment
            if len(videoEls) > 0:
                AttachmentClass = VideoAttachment
            elif len(gifEls) > 0:
                AttachmentClass = GIFAttachment
            elif len(audioEls) > 0:
                AttachmentClass = AudioAttachment

            

            caption = None
            
            if len(captionEls) > 0:
                caption = self.getText(captionEls[0])
                    
            media = AttachmentClass(ext, data)
            

            message = Message(sender, None, caption, media, None, incoming, starred, False)
            return message
        return None

    def sendKeys(self, element, keys, timeout=30):
        err = self.wrapInTimeout(timeout, element.send_keys, keys)
        return err

    def clear(self, element, timeout=30):
        err = self.wrapInTimeout(timeout, element.clear)
        return err

    def click(self, element, timeout=30):
        err = self.wrapInTimeout(timeout, element.click)
        return err

    def rightClick(self, element, timeout=30):
        err = self.wrapInTimeout(timeout, ActionChains(self.driver).context_click(element).perform)
        return err

    def deleteTempDir(self, timeout=30):
        err = self.wrapInTimeout(timeout, shutil.rmtree, "%s\\rosanna%i" % (self.tmpDir, self.id))
        return err

    def deleteFile(self, file, timeout=30):
        err = self.wrapInTimeout(timeout, os.remove, file)
        return err

    def hoverOver(self, element, timeout=30):
        err = self.wrapInTimeout(timeout, ActionChains(self.driver).move_to_element(element).perform)
        return err

    def runScript(self, script, *args):
        return self.driver.execute_script(script, *args)

    def parseBlob(self, src, div):
        getDataScript = """var xhr = new XMLHttpRequest();
                xhr.open('get', '%s');
                xhr.responseType = 'blob';
                window.currentDiv = arguments[0];
                xhr.onload = function(){
                  var fr = new FileReader();
                  fr.onload = function(){
                    window.currentDiv.innerHTML += "<p id='blobResult' style='display: none'>"+this.result+"</p>";
                  };
                
                  fr.readAsDataURL(xhr.response);
                };
                
                xhr.send();""" %src
        self.runScript(getDataScript, div)
        data = ""
        resultDiv = None
        while len(data) == 0:
            resultDivs = div.find_elements_by_xpath(xpaths["blobResult"])
            if len(resultDivs) > 0:
                resultDiv = resultDivs[0]
                data = resultDiv.get_attribute('innerHTML')
        deleteElScript = "arguments[0].parentNode.removeChild(arguments[0]);"
        self.runScript(deleteElScript, resultDiv)
        return data

    def getQRCode(self):
        worked = False
        qrCode = ""
        while not worked:
            try:
                match, matchIndex = self.findFirstElement([xpaths["qrCode"], xpaths["introImage"]])
                if matchIndex == 0:
                    qrCode = match.get_attribute("src")
                    qrCode = qrCode.split("base64,")[1]
                worked = True    
            except:
                pass
        if qrCode == "":
            return None
        imageBytes = base64.b64decode(qrCode)
        stream = io.BytesIO(imageBytes)
        img = Image.open(stream)
        self.gotQRCode = True
        return img

    def showQRCode(self):
        qrCode = self.getQRCode()
        if qrCode is not None:
            self.qrCodeWindow = QRWindow(qrCode)
            self.qrCodeWindow.start()
            return True
        return False

    def waitForConnection(self):
        self.findElement(xpaths["introImage"])
        
        if self.qrCodeWindow is not None:
            self.qrCodeWindow.stop()
        if self.saveSession:
            storageItems = self.getStorageItems()

            with open("saves/%s.sess"%self.sessionName, "w") as file:
                file.write("")
            for key, value in storageItems:
                with open("saves/%s.sess"%self.sessionName, "a") as file:
                    try:
                        file.write(key + ': ' + value + '\n')
                    except UnicodeEncodeError:
                        pass

    def enqueue(self, command):
        self.queue.push(command)

    def searchContacts(self, name, count, startPosition=0, callback=lambda results: None, bouncer=None):
        name = decode(name)
        args = {"contactName": name,
                "count": count,
                "startPos": startPosition,
                "bouncer": bouncer}
        command = SearchContactCommand(args, callback=lambda x, y: callback(x))
        self.enqueue(command)

    def selectContact(self, name, callback=lambda: None):
        name = decode(name)
        args = {"contactName": name}
        command = SelectContactCommand(args, callback=lambda x, y: callback())
        self.enqueue(command)

    def sendMessage(self, name, message, callback=lambda: None):
        name = decode(name)
        message = decode(message)
        args = {"contactName": name,
                "message": message}
        command = SendMessageCommand(args, callback=lambda x, y: callback())
        self.enqueue(command)

    def sendPhotoOrVideo(self, name, path, caption="", callback=lambda: None):
        name = decode(name)
        path = os.path.abspath(decode(path))
        caption = decode(caption)
        args = {"contactName": name,
                "path": path,
                "caption": caption}
        command = SendPhotoOrVideoCommand(args, callback=lambda x, y: callback())
        self.enqueue(command)

    def sendDocument(self, name, path, callback=lambda: None):
        name = decode(name)
        path = os.path.abspath(decode(path))
        args = {"contactName": name,
                "path": path}
        command = SendDocumentCommand(args, callback=lambda x, y: callback())
        self.enqueue(command)

    def sendContact(self, recipient, contact, callback=lambda: None):
        name = decode(recipient)
        contact = decode(contact)
        args = {"contactName": name,
                "contact": contact}
        command = SendContactCommand(args, callback=lambda x, y: callback())
        self.enqueue(command)

    def getRecentContacts(self, count, startPosition=0, callback=lambda names: None, bouncer=None):
        args = {"count": count,
                "startPos": startPosition,
                "bouncer": bouncer}
        command = GetRecentContactsCommand(args, callback=lambda names, rosanna: callback(names))
        self.enqueue(command)

    def getRecentMessages(self, name, count, startPosition=0, fast=True, callback=lambda messages: None, bouncer=None, ignoreAttachments=[], ignoreAdditional=[], filters=[], loadContactProfilePictures=False, timeout=30):
        name = decode(name)
        if "All" in ignoreAttachments:
            ignoreAttachments = ["Image", "Sticker", "Video", "Document", "Audio", "GIF"]
        if "All" in ignoreAdditional:
            ignoreAdditional = ["Location", "Contact"]
        args = {"contactName": name,
                "count": count,
                "startPos": startPosition,
                "fast": fast,
                "bouncer": bouncer,
                "ignoreAttachments": ignoreAttachments,
                "ignoreAdditional": ignoreAdditional,
                "filters": filters,
                "loadContactProfilePics": loadContactProfilePictures,
                "timeout": timeout}
        command = GetRecentMessagesCommand(args, callback=lambda messages, rosanna: callback(messages))
        self.enqueue(command)

    def getRecentMedia(self, name, count, startPosition=0, callback=lambda media:None, bouncer=None, filters=[], timeout=30):
        name = decode(name)
        args = {"contactName": name,
                "count": count,
                "startPos": startPosition,
                "bouncer": bouncer,
                "filters": filters,
                "timeout": timeout,
                "target": "Media"}
        command = GetRecentMediaLinksDocsCommand(args, callback=lambda media, rosanna: callback(media))
        self.enqueue(command)

    def getRecentLinks(self, name, count, startPosition=0, callback=lambda links:None, bouncer=None, ignoreAttachments=[], ignoreAdditional=[], filters=[], loadContactProfilePictures=False, stripped=False, timeout=30):
        name = decode(name)
        if "All" in ignoreAttachments:
            ignoreAttachments = ["Image", "Sticker", "Video", "Document", "Audio", "GIF"]
        if "All" in ignoreAdditional:
            ignoreAdditional = ["Location", "Contact"]
        args = {"contactName": name,
                "count": count,
                "startPos": startPosition,
                "bouncer": bouncer,
                "ignoreAttachments": ignoreAttachments,
                "ignoreAdditional": ignoreAdditional,
                "filters": filters,
                "loadContactProfilePics": loadContactProfilePictures,
                "stripped": stripped,
                "timeout": timeout,
                "target": "Links"}
        command = GetRecentMediaLinksDocsCommand(args, callback=lambda links, rosanna: callback(links))
        self.enqueue(command)

    def getRecentDocuments(self, name, count, startPosition=0, callback=lambda documents:None, bouncer=None, ignoreAttachments=[], ignoreAdditional=[], filters=[], loadContactProfilePictures=False, stripped=False, timeout=30):
        name = decode(name)
        if "All" in ignoreAttachments:
            ignoreAttachments = ["Image", "Sticker", "Video", "Document", "Audio", "GIF"]
        if "All" in ignoreAdditional:
            ignoreAdditional = ["Location", "Contact"]
        args = {"contactName": name,
                "count": count,
                "startPos": startPosition,
                "bouncer": bouncer,
                "ignoreAttachments": ignoreAttachments,
                "ignoreAdditional": ignoreAdditional,
                "filters": filters,
                "loadContactProfilePics": loadContactProfilePictures,
                "stripped": stripped,
                "timeout": timeout,
                "target": "Documents"}
        command = GetRecentMediaLinksDocsCommand(args, callback=lambda docs, rosanna: callback(docs))
        self.enqueue(command)

    def getRecentStarredMessages(self, name, count, startPosition=0, callback=lambda starred:None, bouncer=None, ignoreAttachments=[], ignoreAdditional=[], filters=[], loadContactProfilePictures=False, timeout=30):
        name = decode(name)
        if "All" in ignoreAttachments:
            ignoreAttachments = ["Image", "Sticker", "Video", "Document", "Audio", "GIF"]
        if "All" in ignoreAdditional:
            ignoreAdditional = ["Location", "Contact"]
        args = {"contactName": name,
                "count": count,
                "startPos": startPosition,
                "bouncer": bouncer,
                "ignoreAttachments": ignoreAttachments,
                "ignoreAdditional": ignoreAdditional,
                "filters": filters,
                "loadContactProfilePics": loadContactProfilePictures,
                "timeout": timeout}
        command = GetRecentStarredCommand(args, callback=lambda messages, rosanna: callback(messages))
        self.enqueue(command)

    def getContactDetails(self, name, callback, timeout=30):
        name = decode(name)
        args = {"contactName": name,
                "timeout": timeout}
        command = GetContactDetailsCommand(args, callback=lambda contact, rosanna: callback(contact))
        self.enqueue(command)

    def getMyContactDetails(self, callback, timeout=30):
        args = {"timeout": timeout}
        command = GetMyContactDetailsCommand(args, callback=lambda contact, rosanna: callback(contact))
        self.enqueue(command)

    def setMyName(self, name, callback=lambda: None, timeout=30):
        name = decode(name)
        args = {"name": name,
                "timeout": timeout}
        command = SetMyNameCommand(args, callback=lambda rosanna: callback())
        self.enqueue(command)

    def setMyDescription(self, description, callback=lambda: None, timeout=30):
        description = decode(description)
        args = {"description": description,
                "timeout": timeout}
        command = SetMyDescriptionCommand(args, callback=lambda rosanna: callback())
        self.enqueue(command)

    def setMyProfilePicture(self, path, zoom=0, callback=lambda: None, timeout=30):
        path = os.path.abspath(decode(path))
        args = {"path": path,
                "zoom": zoom,
                "timeout": timeout}
        command = SetMyProfilePictureCommand(args, callback=lambda rosanna: callback())
        self.enqueue(command)

    def run(self):
        self.started = True
        while not self.stopped:
            if not self.queue.empty():
                command = self.queue.pop()
                self.currentCommand = command
                command.execute(self)
        self.driver.quit()
        self.deleteTempDir()


    def stop(self):
        self.stopped = True
        if not self.started:
            self.driver.quit()
            self.deleteTempDir()

    def queueStop(self):
        self.enqueue(StopCommand({}))


class Bouncer:
    def __init__(self, passive=False, counter=False):
        self.lock = Lock()
        self.count = 0
        self.position = 0
        if counter:
            passive = True
        self.passive = passive
        self.counter = counter

        self.register = None
        self.next = None

        self.holding = False
        self.done = False

        self.interrupted = False

    def getCount(self):
        return self.count

    def getPosition(self):
        return self.position

    def enqueue(self, val, inter, position):
        with self.lock:
            self.count += 1
            self.register = [val, inter]
            self.position = position
            if not self.counter:
                self.holding = True

    def getNext(self):
        while self.register is None and not self.done:
            pass
        data = None
        with self.lock:
            self.next = self.register
            self.register = None
            if self.passive:
                self.holding = False
        return self.next

    def release(self):
        with self.lock:
            self.holding = False

    def interrupt(self):
        self.interrupted = True
        self.done = True
        self.holding = False

class Interactable:
    def __init__(self, type, rosanna, container):
        self.type = type
        self.rosanna = rosanna
        self.container = container

class MessageInteractable:
    def __init__(self, rosanna, div):
        Interactable.__init__(self, "Message", rosanna, div)
        self.replying = False

    def openContextMenu(self):
        smaller = self.rosanna.findElement(xpaths["messageSmallerDiv"], base=self.container)
        self.rosanna.hoverOver(smaller)
        arrow = self.rosanna.findElement(xpaths["contextArrow"], base=self.container)
        self.rosanna.click(arrow)

    def read(self, ignoreAttachments=[], ignoreAdditional=[], loadContactProfilePictures=False, timeout=30, args=None):
        if args is None:
            if "All" in ignoreAttachments:
                ignoreAttachments = ["Image", "Sticker", "Video", "Document", "Audio", "GIF"]
            if "All" in ignoreAdditional:
                ignoreAdditional = ["Location", "Contact"]
            args = {"ignoreAttachments": ignoreAttachments,
                    "ignoreAdditional": ignoreAdditional,
                    "loadContactProfilePics": loadContactProfilePictures,
                    "timeout": timeout}

        return self.rosanna.loadMessageFromDiv(self.container, args)

    def toggleStar(self):
        message = self.read(ignoreAttachments=["All"], ignoreAdditional=["All"])
        starred = message.starred
        self.openContextMenu()

        starButton = self.rosanna.findElement(xpaths["starMessageButton"])
        self.rosanna.click(starButton)

        popup = self.rosanna.findElement(xpaths["documentPopup"])
        self.rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0]);", popup)

        while starred == message.starred:
            message = self.read(ignoreAttachments=["All"], ignoreAdditional=["All"])

    def startReply(self):
        self.replying = True
        self.openContextMenu()
        
        replyButton = self.rosanna.findElement(xpaths["replyButton"])
        self.rosanna.click(replyButton)

        self.rosanna.findElement(xpaths["replyingBar"])
        

    def endReply(self):
        window = self.rosanna.findElement(xpaths["messageWindow"])
        divs = self.rosanna.findElements(xpaths["messageDiv"], base=window)
        div = divs[-1]
            
        self.rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0])", div)
        if type(self.rosanna.currentCommand) == GetRecentMessagesCommand:
            self.rosanna.currentCommand.notifyOfDeletedDiv()

        self.replying = False

    
    def reply(self, text):
        text=decode(text)

        self.startReply()

        args = {"contactName": self.rosanna.currentContact,
                "message": text}
        command = SendMessageCommand(args, callback=lambda x, y: self.endReply())
        command.execute(self.rosanna)

        while self.replying:
            pass

    def replyPhotoOrVideo(self, path, caption=""):
        path = os.path.abspath(path)

        self.startReply()

        args = {"contactName": self.rosanna.currentContact,
                "path": path,
                "caption": caption}
        command = SendPhotoOrVideoCommand(args, callback=lambda x, y: self.endReply())
        command.execute(self.rosanna)

        while self.replying:
            pass

    def replyDocument(self, path):
        path = os.path.abspath(path)

        self.startReply()

        args = {"contactName": self.rosanna.currentContact,
                "path": path}
        command = SendDocumentCommand(args, callback=lambda x, y: self.endReply())
        command.execute(self.rosanna)

        while self.replying:
            pass

    def replyContact(self, contact):
        contact = decode(contact)

        self.startReply()

        args = {"contactName": self.rosanna.currentContact,
                "contact": contact}
        command = SendContactCommand(args, callback=lambda x, y: self.endReply())
        command.execute(self.rosanna)

        while self.replying:
            pass

        
    def delete(self, forEveryone):

        if not forEveryone:
            self.rosanna.runScript("arguments[0].insertAdjacentHTML(\"afterend\", \"<div @id='placeholder' style='display: none;'></div>\");", self.container)
        
        self.openContextMenu()

        deleteButton = self.rosanna.findElement(xpaths["deleteMessageButton"])
        self.rosanna.click(deleteButton)

        popup = self.rosanna.findElement(xpaths["deletePopup"])

        buttons, matchIndex = self.rosanna.findFirstElements([xpaths["deleteMessageButtons"], xpaths["deleteMessageLimitedButtons"]], base=popup)
        button = None
        toReturn = True
        if matchIndex == 0:
            button = buttons[2 if forEveryone else 0]
        if matchIndex == 1:
            button = buttons[0 if forEveryone else 1]
            if forEveryone:
                toReturn = False


        self.rosanna.click(button)

        if matchIndex == 0 and forEveryone:
            popup = self.rosanna.findElement(xpaths["deletePopup"])
            confirmButton = popup.find_elements_by_xpath(xpaths["deleteMessageLimitedButtons"])
            if len(confirmButton) > 0:
                self.rosanna.click(confirmButton[1])
        
        popup = [None]
        while len(popup) > 0:
            popup = self.rosanna.driver.find_elements_by_xpath(xpaths["deletePopup"])

        listLoading = [None]
        window = self.rosanna.findElement(xpaths["messageWindow"])
        strikes = 0
        while strikes < 3:
            listLoading = window.find_elements_by_xpath(xpaths["listLoading"])
            returnButtons = self.rosanna.driver.find_elements_by_xpath(xpaths["returnToBottomButton"])
            if len(returnButtons) > 0:
                self.rosanna.click(returnButtons[0])
            strikes += 1
            if len(listLoading) > 0:
                try:
                    for loading in listLoading:
                        if loading.is_displayed():
                            strikes = 0
                except StaleElementReferenceException:
                    strikes = 0

        docPop = self.rosanna.driver.find_elements_by_xpath(xpaths["documentPopup"])
        if len(docPop) > 0:
            self.rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0])", docPop[0])

        return toReturn
        

    def traceReply(self):
        replies = self.container.find_elements_by_xpath(xpaths["replyingTo"])
        if len(replies) > 0:
            self.rosanna.click(replies[0])
            styled = self.rosanna.findElement(xpaths["velocityDiv"])
            messageDiv = self.rosanna.findElement(xpaths["parent"], base=styled)
            self.rosanna.runScript("arguments[0].removeAttribute('style')", styled)
            popups = self.rosanna.driver.find_elements_by_xpath(xpaths["documentPopup"])
            if len(popups) > 0:
                self.rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0]);", popups[0])
                return None
            newInter = MessageInteractable(self.rosanna, messageDiv)
            return newInter
        return None

class MediaInteractable:
    def __init__(self, rosanna, wrapper):
        Interactable.__init__(self, "Media", rosanna, wrapper)

    def read(self, timeout=30, args=None):
        if args is None:
            args = {"timeout": timeout}
        return self.rosanna.loadMediaFromWrapper(self.container, args)

    def getMessageInteractable(self):
        goToMessageButton = self.rosanna.findElement(xpaths["goToMessageButton"])
        self.rosanna.click(goToMessageButton)
        styled = self.rosanna.findElement(xpaths["velocityDiv"])
        messageDiv = self.rosanna.findElement(xpaths["parent"], base=styled)
        self.rosanna.runScript("arguments[0].removeAttribute('style')", styled)

        return MessageInteractable(self.rosanna, messageDiv)

    def returnToPosition(self):
        if type(self.rosanna.currentCommand) == GetRecentMediaLinksDocsCommand:
            position = self.rosanna.currentCommand.position
            wrapper = self.rosanna.findElement(xpaths["previewContainer"])
            previews = self.rosanna.findElements(xpaths["mediaPreviewDiv"])
            while len(previews) <= position:
                self.rosanna.runScript("arguments[0].scrollTop = arguments[0].scrollHeight", wrapper)
                self.rosanna.waitForLoading(base=wrapper)
                previews = self.rosanna.findElements(xpaths["mediaPreviewDiv"])
            self.rosanna.click(previews[position])
            wrappers = []
            while len(wrappers) == 0:
                wrappers = self.rosanna.driver.find_elements_by_xpath(xpaths["mediaWrapper"])

    def toggleStar(self):
        message = self.read()
        starred = message.starred

        starButton = self.rosanna.findElement(xpaths["starMediaButton"])
        self.rosanna.click(starButton)

        docPop = self.rosanna.findElement(xpaths["documentPopup"])
        self.rosanna.runScript("arguments[0].parentNode.removeChild(arguments[0])", docPop)

        while starred == message.starred:
            message = self.read()

    def reply(self, text):
        inter = self.getMessageInteractable()
        inter.reply(text)
        self.returnToPosition()

    def replyPhotoOrVideo(self, path, caption=""):
        inter = self.getMessageInteractable()
        inter.replyPhotoOrVideo(path, caption=caption)
        self.returnToPosition()

    def replyDocument(self, path):
        inter = self.getMessageInteractable()
        inter.replyDocument(path)
        self.returnToPosition()

    def replyContact(self, contact):
        inter = self.getMessageInteractable()
        inter.replyContact(contact)
        self.returnToPosition()


    def delete(self, forEveryone):
        inter = self.getMessageInteractable()
        inter.delete(forEveryone)
        if type(self.rosanna.currentCommand) == GetRecentMediaLinksDocsCommand:
            self.rosanna.currentCommand.notifyOfDeletion()
        self.returnToPosition()

class ContactInteractable:
    def __init__(self, rosanna, result):
        Interactable.__init__(self, "Contact", rosanna, result)

    def read(self):
        return self.rosanna.findElement(xpaths["sendContactSearchMatch"], base=self.container).get_attribute("title")
    
    def select(self):
        self.rosanna.click(self.container)
