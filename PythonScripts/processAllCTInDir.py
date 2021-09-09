# Windows: Open slicer and enter the command to call this script (me) 
# exec(open(r"C:\Users\Yourname\Documents\MySlicerExtensions\LungCTAnalyzer\PythonScripts\processAllCTInDir.py").read())


"""
      ProcessAllCtInDir
      
      Purpose: 
      Run this script to search a directory for CT data sets according the 
      data structure suggested by @PaoloZaffino,   
      automatically run LungCTAnalyzer on them and save the results.
      
      Prerequisites:
      - Each CT data set needs to be placed in a subdirectory "Pat x" where x is an integer
      - input volumes need to be present in each dir and named as follows: 
              "CT.nrrd", "CT_followup.nrrd", "CT_followup2.nrrd", "CT_followup3.nrrd" 
      - lung masks need to be prepared in each dir with LungCTSegmenter and named:                                                                            
             "LungMasksCT.seg.nrrd","LungMasksCTFollowup.seg.nrrd","LungMasksCTFollowup2.seg.nrrd","LungMasksCTFollowup3.seg.nrrd"
      - Up to three follow up CT's are supported
      - results will be saved as CSV to "results.csv" 
      - all scenes will be saved automatically as a MRB file. 
      
      ProcessAllCtInDir.py was developed by Rudolf Bumm, Kantonsspital Graubünden, Switzerland in 8/2021
      
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

# initial CT only
#cnt= [0]
# initial CT and followup
cnt= [0,1]
# initial CT and followup, followup2
#cnt= [0,1,2]
# initial CT and followup, followup2 and followup3
#cnt= [0,1,2,3]
ctName = ["CT.nrrd","CT_followup.nrrd","CT_followup2.nrrd","CT_followup3.nrrd"]
maskName = ["LungMasksCT.seg.nrrd","LungMasksCTFollowup.seg.nrrd","LungMasksCTFollowup2.seg.nrrd","LungMasksCTFollowup3.seg.nrrd"]
detailedSubsegments = False
shrinkMasks = True
countBullae = False
saveDataFileName = ["results.csv","resultsFollowup.csv","resultsFollowup2.csv","resultsFollowup3.csv"]
saveComment = ["Initial","Followup","Followup2","Followup3"]
sceneFilename = ["saved_scene.mrb", "saved_scene_followup.mrb", "saved_scene_followup2.mrb", "saved_scene_followup3.mrb"]
ctCount=0

import time
startTime = time.time()

do_calc = True 
list_only = False 

for cn in cnt: 
    for filename in glob.iglob(root_dir + '**/*.nrrd', recursive=True):
        pathhead, pathtail = os.path.split(filename)
        if pathtail == ctName[cn]:
            if list_only: 
                print('Found: ' + filename)
            else: 
                slicer.mrmlScene.Clear(0)
                print('Processing: ' + pathhead)
                slicer.mrmlScene.Clear(0)
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
                    sceneSaveFilename = pathhead+"/"+sceneFilename[cn]
                    if slicer.util.saveScene(sceneSaveFilename):
                      logging.info("Scene saved to: {0}".format(sceneSaveFilename))
                    else:
                      logging.error("Scene saving failed") 
                    
        # let slicer process events and update its display
        slicer.app.processEvents()
        
stopTime = time.time()
logging.info('Serial processing completed in {0:.2f} seconds'.format(stopTime-startTime))

