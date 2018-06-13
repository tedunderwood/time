import json, csv, math, os, sys
import numpy as np
import estimatedialog

def zscores(alist):
    alist = np.array(alist)
    alist = (alist - alist.mean()) / alist.std()
    return alist

def removenewline(text):
    text = text.replace('\n', ' ')
    text = text.replace('<pb>', ' ')
    text = text.replace('  ', ' ')
    return text.strip()

def countalpha(text):
    text = removenewline(text)
    words = text.split(' ')
    ctr = 0
    for w in words:
        for c in w:
            if c.isalpha():
                ctr += 1
                break
    return ctr

frames = {0, 1, 14, 15}

wordcountdict = dict()
with open('mastermetadata4.csv', encoding = 'utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        wordcountdict[row['docid']] = int(row['numwords'])

def minejson(jsonobj, hardseeds, outrows, seglevel, color):
    global frames

    for filename, filedict in jsonobj.items():
        date = int(filedict['metadata']['firstpub'])
        title = filedict['metadata']['title']
        times = []
        filetimes = []
        filehardpct = []
        frametimes = []
        nonframetimes = []
        subjectivetimes = []
        ellipsistimes = []
        segdialogpct = []
        segtexts = []

        segments = filedict['segments']
        if len(segments) < 14:
            print(filename, color)
            user = input('Use this?')
            if user != 'y':
                continue

        framewords = 0
        if 'numwords' in filedict['metadata']:
            totalwords = int(filedict['metadata']['numwords'])
        else:
            docid = filename.replace('.txt', '')
            totalwords = wordcountdict[docid]

        for idx, seg in enumerate(segments):
            wordcount = countalpha(seg['text'])
            words = seg['text'].split(' ')
            hardct = 0
            for w in words:
                if w.lower().strip('.,\'"-–:;') in hardseeds:
                    hardct += 1
            if wordcount > 0:
                hardpct = hardct / wordcount
            else:
                hardpct = 'NA'
            if 'narratedtime' in seg:
                time = seg['narratedtime']
                if time > 0 and wordcount > 0:
                    logtime = math.log(time / wordcount)
                    times.append(logtime)
                    filetimes.append(logtime)
                    filehardpct.append(hardpct)
                    segtexts.append(removenewline(seg['text']))
                    totalwordsinseg, dialogwords, totalquotes = estimatedialog.count_dialog(seg['text'].split('\n'))
                    segdialogpct.append(dialogwords / totalwordsinseg)

                    if idx in frames:
                        frametimes.append(time / wordcount)
                        framewords += wordcount
                    else:
                        nonframetimes.append(time / wordcount)

                if 'subjectivetime' in seg and wordcount > 0:
                    stime = seg['subjectivetime']
                    etime = seg['ellipsistime']
                    subjectivetimes.append(stime / wordcount)
                    ellipsistimes.append(etime / wordcount)

        nonframewords = totalwords - framewords
        print(framewords, totalwords)

        if len(times) > 0:
            timezscores = zscores(filetimes)
            hardzscores = zscores(filehardpct)
            for time, timez, hardz, hardraw, segdial, thetext in zip(filetimes, timezscores, hardzscores, filehardpct, segdialogpct, segtexts):
                seglevel.append([title, date, time, timez, hardz, hardraw, segdial, color, thetext])
            meanlogtime = sum(times) / len(times)
            stdtime = np.array(times).std()
            meanhardpct = sum(filehardpct) / len(filehardpct)
            if len(frametimes) > 0 and len(nonframetimes) > 0:
                frameavg = sum(frametimes) / len(frametimes)
                nonframeavg = sum(nonframetimes) / len(nonframetimes)
                frameratio = frameavg / nonframeavg
                nonframelogs = [math.log(x) for x in nonframetimes]
                middletime = np.average(nonframelogs)

                # a weighted average to reflect nonrandom sampling
                middleweight = (nonframewords) / len(nonframetimes)
                frameweight = (framewords) / len(frametimes)
                # number of segments "represented" by each middle sample
                weightvector = [middleweight] * len(nonframetimes)
                weightvector.extend([frameweight] * len(frametimes))
                toaverage = [math.log(x) for x in nonframetimes]
                toaverage.extend([math.log(x) for x in frametimes])
                weightedavg = np.average(toaverage, weights = weightvector)
                meandialog = sum(segdialogpct) / len(segdialogpct)
            else:
                frameratio = 0
                middletime = 0
                weightedavg = 0
            outrows.append([title, date, meanlogtime, middletime, stdtime, meanhardpct, frameratio, weightedavg, meandialog, color])

    return outrows, seglevel

outrows = []

hardseeds = set()
with open('lib/stanford.csv', encoding = 'utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['class'] == 'hard':
            hardseeds.add(row['word'])

seglevel = []

thingstomine = [('rawdata/underwoodpassagesA.json', 'underwood'), 
    ('rawdata/leepassages1A.json', 'lee'), ('rawdata/leepassages2A.json', 'lee'), 
    ('rawdata/mercadopassages1.json', 'mercado'), ('rawdata/mercadomerged.json', 'mercado'), 
    ('rawdata/leepassages3A.json', 'lee'), ('rawdata/leeinterrater.json', 'lee'),
    ('rawdata/mercadointerrater.json', 'mercado'), 
    ('rawdata/underwoodinterrater.json', 'underwood'), ('rawdata/finalpush.json', 'underwood'), 
    ('rawdata/biography.json', 'red')]

for thing, color in thingstomine:
    with open(thing, mode = 'r', encoding = 'utf-8') as f:
        thestring = f.read()
    jsonobj = json.loads(thestring)
    outrows, seglevel = minejson(jsonobj, hardseeds, outrows, seglevel, color)

mergedict = dict()
for row in outrows:
    title = row[0]
    if title not in mergedict:
        mergedict[title] = [row]
    else:
        mergedict[title].append(row)

def themean(sequence):
    return sum(sequence) / len(sequence)

condensedrows = []
for title, rows in mergedict.items():
    if len(rows) < 2:
        condensedrows.append(rows[0])
    else:
        meanlogtimes = []
        stdtimes = []
        meanhardpcts = []
        frameratios = []
        middletimes = []
        weightedaverages = []
        meandialogs = []
        for row in rows:
            meanlogtimes.append(row[2])
            middletimes.append(row[3])
            stdtimes.append(row[4])
            meanhardpcts.append(row[5])
            frameratios.append(row[6])
            weightedaverages.append(row[7])
            meandialogs.append(row[8])
        newrow = [rows[0][0], rows[0][1], themean(meanlogtimes), themean(middletimes), themean(stdtimes), themean(meanhardpcts), themean(frameratios), themean(weightedaverages), themean(meandialogs), rows[0][9]]
        condensedrows.append(newrow)
        print(title)

with open('2018averagetimes.csv', mode = 'w', encoding = 'utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['title', 'date', 'meantime', 'middletime', 'stdtime', 'meanhard', 'frameratio', 'weightedavg', 'meandialog', 'col'])
    for row in condensedrows:
        writer.writerow(row)

with open('2018segleveldata.csv', mode = 'w', encoding = 'utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['title', 'date', 'time', 'timez', 'hardz', 'hardraw', 'dialog', 'col', 'text'])
    for row in seglevel:
        writer.writerow(row)



