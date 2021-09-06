# Windoes: Open slicer and enter the command to call this script (me) 
# exec(open(r"C:\Users\Yourname\Documents\MySlicerExtensions\LungCTAnalyzer\PythonScripts\processAllCTInDir.py").read())


"""
      Run this script to search a directory for CT data sets,  
      automatically run LungCTAnalyzer and save the results.
      
      This file was developed by Rudolf Bumm, Kantonsspital Graubünden, Switzerland.
      
"""

import glob
import sys
import os
import time

import LungCTAnalyzer

from LungCTAnalyzer import LungCTAnalyzerTest
from LungCTAnalyzer import LungCTAnalyzerLogic


# root_dir needs a trailing slash (i.e. /root/dir/)
root_dir = "D:/Patients5/"
slicer.mrmlScene.Clear(0)

slicer.util.selectModule('LungCTAnalyzer')

cnt= [0,1,2,3]
ctName = ["CT.nrrd","CT_followup.nrrd","CT_followup2.nrrd","CT_followup3.nrrd"]
maskName = ["LungMasksCT.seg.nrrd","LungMasksCTFollowup.seg.nrrd","LungMasksCTFollowup2.seg.nrrd","LungMasksCTFollowup3.seg.nrrd"]
detailedSubsegments = False
shrinkMasks = True
countBullae = False
saveDataFileName = ["results.csv","resultsFollowup.csv","resultsFollowup2.csv","resultsFollowup3.csv"]
saveComment = ["Initial","Followup","Followup2","Followup3"]
sceneFilename = "saved_scene.mrb"
ctCount=0

import time
startTime = time.time()
do_calc = True 
for filename in glob.iglob(root_dir + '**/*.nrrd', recursive=True):
    pathhead, pathtail = os.path.split(filename)        
    for cn in cnt: 
        if pathtail == ctName[cn]:
            slicer.mrmlScene.Clear(0)
            print('Processing: ' + pathhead)
            loadedVolumeNode = slicer.util.loadVolume(filename)
            loadedMaskNode = slicer.util.loadSegmentation(pathhead+"/"+maskName[cn])  
            
            loadedMaskNode.SetName("Lung segmentation")
            ctCount += 1
            
            logic = LungCTAnalyzerLogic()

            logic.inputVolume = loadedVolumeNode
            logic.inputSegmentation = loadedMaskNode
            logic.rightLungMaskSegmentID = loadedMaskNode.GetSegmentation().GetSegmentIdBySegmentName("right lung")
            logic.leftLungMaskSegmentID = loadedMaskNode.GetSegmentation().GetSegmentIdBySegmentName("left lung")
            logic.setDefaultThresholds(-1050,-990,-650,-400,0,3000)
            
            logic.detailedSubsegments = detailedSubsegments
            logic.shrinkMasks = shrinkMasks
            logic.countBullae = countBullae
            if do_calc: 
                # show input segments to enable centroid calculation
                logic.inputSegmentation.GetDisplayNode().Visibility2DOn()
                logic.inputSegmentation.GetDisplayNode().Visibility3DOff()

                logic.process() # 3D

                logic.showTable(logic.resultsTable)

                # ensure user sees the new segments
                logic.outputSegmentation.GetDisplayNode().Visibility2DOn()


                # hide preview in slice view
                slicer.util.setSliceViewerLayers(background=logic.inputVolume, foreground=None)
                sys.stdout.flush()
                logic.saveExtendedDataToFile(root_dir + "/"+ saveDataFileName[cn],filename,str(ctCount),saveComment[cn])
                # Save scene
                sceneSaveFilename = pathhead+"/"+sceneFilename
                if slicer.util.saveScene(sceneSaveFilename):
                  logging.info("Scene saved to: {0}".format(sceneSaveFilename))
                else:
                  logging.error("Scene saving failed") 
                
        # let slicer process events and update its display
        slicer.app.processEvents()
        
stopTime = time.time()
logging.info('Processing completed in {0:.2f} seconds'.format(stopTime-startTime))

