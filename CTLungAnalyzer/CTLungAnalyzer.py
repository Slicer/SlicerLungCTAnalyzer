import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# CTLungAnalyzer
#

class CTLungAnalyzer(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Lung CT Analyzer"  # TODO: make this more human readable by adding spaces
    self.parent.categories = ["Chest Imaging Platform"]  # TODO: set categories (folders where the module shows up in the module selector)
    self.parent.dependencies = []  # TODO: add here list of module names that this module requires
    self.parent.contributors = ["Rudolf Bumm (KSGR Switzerland)"]  # TODO: replace with "Firstname Lastname (Organization)"
    # TODO: update with short description of the module and a link to online module documentation
    self.parent.helpText = """
The CT Lung Analyzer is a 3D Slicer extension for segmentation and spatial reconstruction of infiltrated and collapsed areas in chest CT examinations.
See more information in <a href="https://github.com/rbumm/SlicerCTLungAnalyzer">module documentation</a>.
"""
    # TODO: replace with organization, grant and thanks
    self.parent.acknowledgementText = """
This file was originally developed by Rudolf Bumm, Kantonsspital Graubünden, Switzerland. Parts of this code were inspired by a code snippet (https://gist.github.com/lassoan/5ad51c89521d3cd9c5faf65767506b37) of Andras Lasso, PerkLab. 
"""

    # Additional initialization step after application startup is complete
    slicer.app.connect("startupCompleted()", registerSampleData)

#
# Register sample data sets in Sample Data module
#

def registerSampleData():
  """
  Add data sets to Sample Data module.
  """
  # It is always recommended to provide sample data for users to make it easy to try the module,
  # but if no sample data is available then this method (and associated startupCompeted signal connection) can be removed.

  import SampleData
  iconsPath = os.path.join(os.path.dirname(__file__), 'Resources/Icons')

  # To ensure that the source code repository remains small (can be downloaded and installed quickly)
  # it is recommended to store data sets that are larger than a few MB in a Github release.

  # load demo chest CT
  
  SampleData.SampleDataLogic.registerCustomSampleDataSource( 
      category="Lung", 
      sampleName='DemoChestCT',
      uris='http://scientific-networks.com/slicerdata/LungCTAnalyzerChestCT.nrrd',
      fileNames='DemoChestCT.nrrd',
      nodeNames='DemoChestCT',
      thumbnailFileName=os.path.join(iconsPath, 'DemoChestCT.png'),
      loadFileType='VolumeFile',
      checksums='SHA256:9bb74f4383bce0ced80243916e785ce564cc2c8f535e8273da8a04f80dff4287'
      )
  SampleData.SampleDataLogic.registerCustomSampleDataSource( 
      category="Lung", 
      sampleName='DemoLungMasks',
      uris='http://scientific-networks.com/slicerdata/LungCTAnalyzerMaskSegmentation.seg.nrrd',
      fileNames='DemoLungMasks.seg.nrrd',
      nodeNames='DemoLungMasks',
      thumbnailFileName=os.path.join(iconsPath, 'DemoChestCT.png'),
      loadFileType='SegmentationFile',
      checksums='SHA256:76312929a5a17dc5188b268d0cd43dabe9f2e10c4496e71d56ee0be959077bc4'
      )
      
#
# CTLungAnalyzerWidget
#

class CTLungAnalyzerWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  

  
  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False
    

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer).
    # Additional widgets can be instantiated manually and added to self.layout.
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/CTLungAnalyzer.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = CTLungAnalyzerLogic()

    # Connections

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    
    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    self.ui.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.rightLungMaskSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.leftLungMaskSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

    # Buttons
    self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.ui.restoreDefaultsButton.connect('clicked(bool)', self.onRestoreDefaultsButton)
    self.ui.saveThresholdsButton.connect('clicked(bool)', self.onSaveThresholdsButton)
    self.ui.loadThresholdsButton.connect('clicked(bool)', self.onLoadThresholdsButton)
    self.ui.segmentsOnOffButton.connect('clicked(bool)', self.onSegmentsOnOffButton)
    self.ui.dwnlCOVIDDataButton.connect('clicked(bool)', self.ondwnlCOVIDDataButton)
    

    #Range sliders
    self.ui.BullaRangeWidget.connect( 'valuesChanged(double,double)', self.onBullaRangeWidgetChanged )
    self.ui.VentilatedRangeWidget.connect( 'valuesChanged(double,double)', self.onVentilatedRangeWidgetChanged )
    self.ui.InfiltratedRangeWidget.connect( 'valuesChanged(double,double)', self.onInfiltratedRangeWidgetChanged )
    self.ui.CollapsedRangeWidget.connect( 'valuesChanged(double,double)', self.onCollapsedRangeWidgetChanged )
    self.ui.VesselsRangeWidget.connect( 'valuesChanged(double,double)', self.onVesselsRangeWidgetChanged )

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()
    self.initThresholds()
    seg_visible = True


  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()

  def enter(self):
    """
    Called each time the user opens this module.
    """
    # Make sure parameter node exists and observed
    self.initializeParameterNode()

  def exit(self):
    """
    Called each time the user opens a different module.
    """
    # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
    self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

  def onSceneStartClose(self, caller, event):
    """
    Called just before the scene is closed.
    """
    # Parameter node will be reset, do not use it anymore
    self.setParameterNode(None)

  def onSceneEndClose(self, caller, event):
    """
    Called just after the scene is closed.
    """
    # If this module is shown while the scene is closed then recreate a new parameter node immediately
    if self.parent.isEntered:
      self.initializeParameterNode()

  def initializeParameterNode(self):
    """
    Ensure parameter node exists and observed.
    """
    # Parameter node stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.

    self.setParameterNode(self.logic.getParameterNode())

    # Select default input nodes if nothing is selected yet to save a few clicks for the user
    if not self._parameterNode.GetNodeReference("InputVolume"):
      firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
      if firstVolumeNode:
        self._parameterNode.SetNodeReferenceID("InputVolume", firstVolumeNode.GetID())
   # Select default input nodes if nothing is selected yet to save a few clicks for the user


  def setParameterNode(self, inputParameterNode):
    """
    Set and observe parameter node.
    Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    # Unobserve previously selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode
    if self._parameterNode is not None:
      self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update node selectors and sliders
    self.ui.inputVolumeSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputVolume"))
    self.ui.rightLungMaskSelector.setCurrentNode(self._parameterNode.GetNodeReference("RightLungMaskNode"))
    self.ui.leftLungMaskSelector.setCurrentNode(self._parameterNode.GetNodeReference("LeftLungMaskNode"))

 
    # Update buttons states and tooltips
    if self._parameterNode.GetNodeReference("InputVolume") and self._parameterNode.GetNodeReference("RightLungMaskNode") and self._parameterNode.GetNodeReference("LeftLungMaskNode"):
    #if self._parameterNode.GetNodeReference("InputVolume"):
      self.ui.applyButton.toolTip = "Compute input volume"
      self.ui.applyButton.enabled = True
    else:
      self.ui.applyButton.toolTip = "Select input volume and right and left lung mask"
      self.ui.applyButton.enabled = False

    # All the GUI updates are done
    self._updatingGUIFromParameterNode = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """


    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

    self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputVolumeSelector.currentNodeID)
    #slicer.util.infoDisplay(self.ui.rightLungMaskSelector.currentNodeID)
    if self.ui.rightLungMaskSelector.currentNodeID():
        self._parameterNode.SetNodeReferenceID("RightLungMaskNode",str(self.ui.rightLungMaskSelector.currentNodeID()))
    if self.ui.leftLungMaskSelector.currentNodeID():
        self._parameterNode.SetNodeReferenceID("LeftLungMaskNode", str(self.ui.leftLungMaskSelector.currentNodeID()))

    #slicer.util.infoDisplay(self.ui.rightLungMaskSelector.currentNode().GetName())
    #slicer.util.infoDisplay(self.ui.rightLungMaskSelector.currentNode().GetSegmentation().GetSegment(self.ui.rightLungMaskSelector.currentSegmentID()).GetName())
    #slicer.util.infoDisplay(self.ui.rightLungMaskSelector.currentSegmentID())
    #slicer.util.infoDisplay(self.ui.leftLungMaskSelector.currentNodeID())
    #slicer.util.infoDisplay(self.ui.leftLungMaskSelector.currentSegmentID())

    self._parameterNode.EndModify(wasModified)

  def onBullaRangeWidgetChanged(self):
    self.ui.VentilatedRangeWidget.minimumValue = self.ui.BullaRangeWidget.maximumValue 
    if self.ui.BullaRangeWidget.maximumValue > self.ui.VentilatedRangeWidget.minimumValue: 
        self.ui.BullaRangeWidget.maximumValue = self.ui.VentilatedRangeWidget.minimumValue  

  def onVentilatedRangeWidgetChanged(self):
    self.ui.BullaRangeWidget.maximumValue = self.ui.VentilatedRangeWidget.minimumValue 
    if self.ui.VentilatedRangeWidget.maximumValue < self.ui.InfiltratedRangeWidget.minimumValue: 
        self.ui.InfiltratedRangeWidget.minimumValue = self.ui.VentilatedRangeWidget.maximumValue  
    if self.ui.VentilatedRangeWidget.maximumValue > self.ui.InfiltratedRangeWidget.minimumValue: 
        self.ui.InfiltratedRangeWidget.minimumValue = self.ui.VentilatedRangeWidget.maximumValue  
    if self.ui.VentilatedRangeWidget.maximumValue > self.ui.InfiltratedRangeWidget.maximumValue: 
        self.ui.VentilatedRangeWidget.maximumValue = self.ui.InfiltratedRangeWidget.maximumValue  

  def onInfiltratedRangeWidgetChanged(self):
    self.ui.VentilatedRangeWidget.maximumValue = self.ui.InfiltratedRangeWidget.minimumValue 
    if self.ui.InfiltratedRangeWidget.maximumValue > self.ui.CollapsedRangeWidget.minimumValue: 
        self.ui.CollapsedRangeWidget.minimumValue = self.ui.InfiltratedRangeWidget.maximumValue  
    if self.ui.InfiltratedRangeWidget.minimumValue < self.ui.VentilatedRangeWidget.minimumValue: 
        self.ui.InfiltratedRangeWidget.minimumValue = self.ui.VentilatedRangeWidget.minimumValue  
    self.ui.CollapsedRangeWidget.minimumValue = self.ui.InfiltratedRangeWidget.maximumValue 

  def onCollapsedRangeWidgetChanged(self):
    self.ui.InfiltratedRangeWidget.maximumValue = self.ui.CollapsedRangeWidget.minimumValue 
    if self.ui.CollapsedRangeWidget.maximumValue > self.ui.VesselsRangeWidget.minimumValue: 
        self.ui.VesselsRangeWidget.minimumValue = self.ui.CollapsedRangeWidget.maximumValue  
    if self.ui.CollapsedRangeWidget.minimumValue < self.ui.InfiltratedRangeWidget.minimumValue: 
        self.ui.CollapsedRangeWidget.minimumValue = self.ui.InfiltratedRangeWidget.minimumValue  
    self.ui.VesselsRangeWidget.minimumValue = self.ui.CollapsedRangeWidget.maximumValue 

  def onVesselsRangeWidgetChanged(self):
    self.ui.CollapsedRangeWidget.maximumValue = self.ui.VesselsRangeWidget.minimumValue 
    if self.ui.VesselsRangeWidget.minimumValue < self.ui.CollapsedRangeWidget.minimumValue: 
        self.ui.VesselsRangeWidget.minimumValue = self.ui.CollapsedRangeWidget.minimumValue  

  def initThresholds(self):
    #slicer.util.infoDisplay("Test")
    logging.info('Restoring defaults')
    self.ui.BullaRangeWidget.minimumValue = -1000.0
    self.ui.BullaRangeWidget.maximumValue = -950.
    self.ui.VentilatedRangeWidget.minimumValue = -950.0
    self.ui.VentilatedRangeWidget.maximumValue = -750.
    self.ui.InfiltratedRangeWidget.minimumValue = -750.0
    self.ui.InfiltratedRangeWidget.maximumValue = -400.
    self.ui.CollapsedRangeWidget.minimumValue = -400.0
    self.ui.CollapsedRangeWidget.maximumValue = 0.0
    self.ui.VesselsRangeWidget.minimumValue = 0.0
    self.ui.VesselsRangeWidget.maximumValue = 2999.


  def onSaveThresholdsButton(self):
    #slicer.util.infoDisplay("Test")
    logging.info('Storing defaults')
    import configparser
    config = configparser.ConfigParser()
    #logging.info('Found:' + ctn.GetName())
    #print(config['DEFAULT']['path'])     # -> "/path/name/"
    config['DEFAULT']['BullaMinimum'] =  str(self.ui.BullaRangeWidget.minimumValue)    # update
    config['DEFAULT']['BullaMaximum'] =  str(self.ui.BullaRangeWidget.maximumValue)    # update
    config['DEFAULT']['VentilatedMinimum'] =  str(self.ui.VentilatedRangeWidget.minimumValue)    # update
    config['DEFAULT']['VentilatedMaximum'] =  str(self.ui.VentilatedRangeWidget.maximumValue)    # update
    config['DEFAULT']['InfiltratedMinimum'] =  str(self.ui.InfiltratedRangeWidget.minimumValue)    # update
    config['DEFAULT']['InfiltratedMaximum'] =  str(self.ui.InfiltratedRangeWidget.maximumValue)    # update
    config['DEFAULT']['CollapsedMinimum'] =  str(self.ui.CollapsedRangeWidget.minimumValue)    # update
    config['DEFAULT']['CollapsedMaximum'] =  str(self.ui.CollapsedRangeWidget.maximumValue)    # update
    config['DEFAULT']['VesselsMinimum'] =  str(self.ui.VesselsRangeWidget.minimumValue)    # update
    config['DEFAULT']['VesselsMaximum'] =  str(self.ui.VesselsRangeWidget.maximumValue)    # update
    config['DEFAULT']['default_message'] = 'Thank you for using CTLungAnalyzer!'   # create
    with open('CTLungAnalyzer.ini', 'w') as configfile:    # save
        config.write(configfile)

  def onLoadThresholdsButton(self):
    #slicer.util.infoDisplay("Test")
    logging.info('Loading defaults')
    self.initThresholds()
    import configparser
    config = configparser.ConfigParser()
    config.read('CTLungAnalyzer.ini')
    #logging.info('Found:' + ctn.GetName())
    #print(config['DEFAULT']['path'])     # -> "/path/name/"
    self.ui.BullaRangeWidget.minimumValue = float(config['DEFAULT']['BullaMinimum'])
    self.ui.BullaRangeWidget.maximumValue = float(config['DEFAULT']['BullaMaximum'])
    self.ui.VentilatedRangeWidget.minimumValue = float(config['DEFAULT']['VentilatedMinimum'])
    self.ui.VentilatedRangeWidget.maximumValue = float(config['DEFAULT']['VentilatedMaximum'])
    self.ui.InfiltratedRangeWidget.minimumValue = float(config['DEFAULT']['InfiltratedMinimum'])
    self.ui.InfiltratedRangeWidget.maximumValue = float(config['DEFAULT']['InfiltratedMaximum'])
    self.ui.CollapsedRangeWidget.minimumValue = float(config['DEFAULT']['CollapsedMinimum'])
    self.ui.CollapsedRangeWidget.maximumValue = float(config['DEFAULT']['CollapsedMaximum'])
    self.ui.VesselsRangeWidget.minimumValue = float(config['DEFAULT']['VesselsMinimum'])
    self.ui.VesselsRangeWidget.maximumValue = float(config['DEFAULT']['VesselsMaximum'])
    
  def onRestoreDefaultsButton(self):
    #slicer.util.infoDisplay("Test")
    logging.info('Restoring defaults')
    self.initThresholds()


  def ondwnlCOVIDDataButton(self):
    #slicer.util.infoDisplay("Test")
    if slicer.util.confirmYesNoDisplay("This will clear all data in your current storage node. Are you sure ?", windowTitle=None, parent=None):
        logging.info('Clearing the MRLM node')
        slicer.mrmlScene.Clear()
        import SampleData
        logging.info('Registering the sample data')
        registerSampleData()
        logging.info('Downloading COVID Chest CT dataset')
        inputVolume = SampleData.downloadSample('DemoChestCT')
        logging.info('Downloading COVID Lung Mask segmentation')
        lungMaskSegmentation = SampleData.downloadSample('DemoLungMasks')
        logging.info('Centering.')
        # center viewports
        slicer.app.applicationLogic().FitSliceToAll()
        # center 3D view
        layoutManager = slicer.app.layoutManager()
        threeDWidget = layoutManager.threeDWidget(0)
        threeDView = threeDWidget.threeDView()
        threeDView.resetFocalPoint()
        logging.info('Normal end of loading procedure.')
    else: 
        logging.info('Aborted.')
    



  def onSegmentsOnOffButton(self):
    if segmentationDisplayNode.GetVisibility2D(): 
        logging.info('Segments visibility off')
        segmentationDisplayNode.Visibility2DOff()
    else : 
        logging.info('Segments visibility on')
        segmentationDisplayNode.Visibility2DOn()
        


  def onApplyButton(self):
    """
    Run processing when user clicks "Apply" button.
    """
    try:

      # Compute output
      self.logic.process(self.ui.inputVolumeSelector.currentNode(),
      self.ui.rightLungMaskSelector.currentNode(),
      self.ui.leftLungMaskSelector.currentNode(),
      self.ui.rightLungMaskSelector.currentSegmentID(),
      self.ui.leftLungMaskSelector.currentSegmentID(),
      self.ui.BullaRangeWidget.minimumValue,
      self.ui.BullaRangeWidget.maximumValue,
      self.ui.VentilatedRangeWidget.minimumValue,
      self.ui.VentilatedRangeWidget.maximumValue,
      self.ui.InfiltratedRangeWidget.minimumValue,
      self.ui.InfiltratedRangeWidget.maximumValue,
      self.ui.CollapsedRangeWidget.minimumValue,
      self.ui.CollapsedRangeWidget.maximumValue,
      self.ui.VesselsRangeWidget.minimumValue,
      self.ui.VesselsRangeWidget.maximumValue,
      self.ui.generateStatisticsCheckBox.checked,
      self.ui.deletePreviousSegmentationsCheckBox.checked,
      self.ui.includeCovidEvaluationCheckBox.checked,
      self.ui.show3DCheckBox.checked
      )
      #logging.info('Apply button')


    except Exception as e:
      slicer.util.errorDisplay("Failed to compute results: "+str(e))
      import traceback
      traceback.print_exc()


#
# CTLungAnalyzerLogic
#

class CTLungAnalyzerLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self):
    """
    Called when the logic class is instantiated. Can be used for initializing member variables.
    """
    logging.info('_init_')
    ScriptedLoadableModuleLogic.__init__(self)
 

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    logging.info('setDefaultParameters')
    if not parameterNode.GetParameter("Threshold"):
      parameterNode.SetParameter("Threshold", "100.0")
    if not parameterNode.GetParameter("Invert"):
      parameterNode.SetParameter("Invert", "false")

  def process(self, inputVolume, rightLungMaskNode, leftLungMaskNode, rightLungMaskID, leftLungMaskID, bullMin,bullMax,ventMin,ventMax,infMin,infMax,collMin,collMax, vessMin, vessMax, genstat_cb, delprev_cb, inccov_cb, show3D_cb):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param inputVolume: volume to be thresholded
    """
    logging.info('Processing started.')

    if not inputVolume:
      raise ValueError("Input volume is invalid")
    logging.info('Input present.')

    import time
    startTime = time.time()


    # Compute 
    masterVolumeNode = inputVolume

    if delprev_cb: 
        # Delete previous clutter segments if present (and requested) 
        logging.info('Delete clutter segments ....')
        allSegmentNodes = slicer.util.getNodes('vtkMRMLSegmentationNode*').values()
        for ctn in allSegmentNodes:
          #logging.info('Name:>' + ctn.GetName()+'<')
          teststr = ctn.GetName()
          if 'Segmentation_' in teststr:
            #logging.info('Found:' + ctn.GetName())
            if not (teststr == rightLungMaskNode.GetName() or teststr == leftLungMaskNode.GetName()):
                #do not delete the lung mask segmentation if its name is in the format 'Segmentation_'
                slicer.mrmlScene.RemoveNode(ctn)
            #break        

    #slicer.mrmlScene.RemoveNode(slicer.util.getNode('Right lung masked volume'))
    logging.info('Delete old lungmask volumes ....')
    slicer.mrmlScene.RemoveNode(slicer.mrmlScene.GetFirstNodeByName('Right lung masked volume'))
    slicer.mrmlScene.RemoveNode(slicer.mrmlScene.GetFirstNodeByName('Left lung masked volume'))


    #slicer.util.infoDisplay(rightLungMaskNode.GetSegmentation().GetSegment(rightLungMaskID).GetName())
    
    logging.info('Check right lung mask present ....')
    if rightLungMaskNode.GetSegmentation().GetSegment(rightLungMaskID).GetName().upper() != "RIGHT LUNG MASK":
        raise ValueError("You did not pick a segmentation with the name 'Right lung ´mask' in the mandatory drop down field. Procedure aborted.")    

    logging.info('Check left lung mask present ....')
    if rightLungMaskNode.GetSegmentation().GetSegment(leftLungMaskID).GetName().upper() != "LEFT LUNG MASK":
        raise ValueError("You did not pick a segmentation with the name 'Left lung mask' in the mandatory drop down field. Procedure aborted.")    
   
    # Create segmentation
    #try: 
    #    maskSegmentationNode = slicer.util.getNode('Segmentation')
    #except Exception as e:
    #  slicer.util.errorDisplay("Failed to compute results: "+str(e))
    #  slicer.util.confirmOkCancelDisplay("Help on this error: Unable to find mask segmentation node. This module needs a 3D slicer node 'Segmentation' with two segments: 'Right lung mask' (1st segment) and 'Left lung mask' (2nd segment). Please prepare this node now and run the module again.")
    #  import traceback
    #  traceback.print_exc()
    #  raise ValueError("Procedure is cancelled.")    
    
    logging.info('Add segmentation node ....')
    segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        
    #segmentationNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentationNode")
    #segmentationNode = slicer.util.getNode('Segmentation')
    
    logging.info('Create default display ....')
    segmentationNode.CreateDefaultDisplayNodes() # only needed for display
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(masterVolumeNode)

    # Create temporary segment editor to get access to effects
    logging.info('Create temporary segment editor ....')
    segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
    segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
    segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
    #segmentEditorNode.SetMaskSegmentID(segmentationNode.GetSegmentation().GetNthSegmentID(0))
    #segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteAllSegments)
    #segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentEditorNode.PaintAllowedInsideSingleSegment)
    if not segmentEditorWidget.effectByName("Mask volume"):
        slicer.util.errorDisplay("Please install 'SegmentEditorExtraEffects' extension using Extension Manager.")

    logging.info('Get Display node ....')
    global segmentationDisplayNode
    segmentationDisplayNode=segmentationNode.GetDisplayNode()
    logging.info('Get segmentation ....')
    segmentation=segmentationNode.GetSegmentation()

    # Create a lung volume
    # This has to be done because of a bug within slicer. 
    # If you don't do this, the segmenteditorWidget will present an exception like error message
    # but only on the first try  
    
    logging.info('Create false lung volume ....')
    # Create right lung volume
    segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)
    segmentEditorWidget.setSegmentationNode(rightLungMaskNode)
    segmentEditorWidget.setCurrentSegmentID(rightLungMaskID)
    # Set up masking parameters
    segmentEditorWidget.setActiveEffectByName("Mask volume")
    effect = segmentEditorWidget.activeEffect()
    segmentEditorNode.SetMaskSegmentID(rightLungMaskID)
    segmentEditorNode.SetMasterVolumeIntensityMask(False)
    #segmentEditorNode.SetMasterVolumeIntensityMask(True)
    #segmentEditorNode.SetMasterVolumeIntensityMaskRange(6900, 7000)
    effect.setParameter("Operation", "FILL_OUTSIDE")
    effect.setParameter("FillValue", str(inputVolume.GetImageData().GetScalarRange()[0]))
    #effect.setParameter("FillValue", "3000")
    falseMaskedVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "False lung masked volume")
    effect.self().outputVolumeSelector.setCurrentNode(falseMaskedVolume)
    effect.self().onApply()

    logging.info('Create right lung volume ....')
    # Create right lung volume
    segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)
    segmentEditorWidget.setSegmentationNode(rightLungMaskNode)
    segmentEditorWidget.setCurrentSegmentID(rightLungMaskID)
    # Set up masking parameters
    segmentEditorWidget.setActiveEffectByName("Mask volume")
    effect = segmentEditorWidget.activeEffect()
    segmentEditorNode.SetMaskSegmentID(rightLungMaskID)
    segmentEditorNode.SetMasterVolumeIntensityMask(False)
    #segmentEditorNode.SetMasterVolumeIntensityMask(True)
    #segmentEditorNode.SetMasterVolumeIntensityMaskRange(6900, 7000)
    effect.setParameter("Operation", "FILL_OUTSIDE")
    effect.setParameter("FillValue", str(inputVolume.GetImageData().GetScalarRange()[0]))
    #effect.setParameter("FillValue", "3000")
    rightMaskedVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Right lung masked volume")
    effect.self().outputVolumeSelector.setCurrentNode(rightMaskedVolume)
    effect.self().onApply()

    logging.info('Create left lung volume ....')
    # Create left lung volume
    segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)
    segmentEditorWidget.setSegmentationNode(leftLungMaskNode)
    segmentEditorWidget.setCurrentSegmentID(leftLungMaskID)
    # Set up masking parameters
    segmentEditorWidget.setActiveEffectByName("Mask volume")
    effect = segmentEditorWidget.activeEffect()
    segmentEditorNode.SetMaskSegmentID(leftLungMaskID)
    segmentEditorNode.SetMasterVolumeIntensityMask(False)
    #segmentEditorNode.SetMasterVolumeIntensityMask(True)
    #segmentEditorNode.SetMasterVolumeIntensityMaskRange(6900, 7000)
    effect.setParameter("Operation", "FILL_OUTSIDE")
    effect.setParameter("FillValue", str(inputVolume.GetImageData().GetScalarRange()[0]))
    #effect.setParameter("FillValue", "3000")
    leftMaskedVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Left lung masked volume")
    effect.self().outputVolumeSelector.setCurrentNode(leftMaskedVolume)
    effect.self().onApply()
    
    logging.info('Create right lung segments ....')
    segmentEditorWidget.setMasterVolumeNode(rightMaskedVolume)
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(rightMaskedVolume)
    segmentEditorWidget.setSegmentationNode(segmentationNode)

    # Create segments by thresholding
    segmentsFromHounsfieldUnits = [
        ["Emphysema right", 0.0,0.0,0.0],
        ["Ventilated right", 0.0,0.5,1.0],
        ["Infiltration right", 1.0,0.5,0.0],
        ["Collapsed right", 1.0,0.0,1.0],
        ["Vessels right", 1.0,0.0,0.0] ]

    #for segmentName, thresholdMin, thresholdMax, r, g, b in segmentsFromHounsfieldUnits:
        # Delete previous segments
        #logging.info('Deleting segment.')
        #segmentId = segmentation.GetSegmentIdBySegmentName(segmentName)
        #segmentation.RemoveSegment(segmentId)
        
    for segmentName, r, g, b in segmentsFromHounsfieldUnits:
        # Create segment
        logging.info('Creating segment.')
        addedSegmentID = segmentationNode.GetSegmentation().AddEmptySegment(segmentName)
        segmentEditorNode.SetSelectedSegmentID(addedSegmentID)
        # Set color
        #logging.info('Setting segment color.')
        segmentId = segmentation.GetSegmentIdBySegmentName(segmentName)
        segmentationDisplayNode.SetSegmentOpacity3D(segmentId,0.2)
        #segmentationDisplayNode.SetSegmentOpacity(segmentId,1.)
        segmentationDisplayNode.SetSegmentOpacity2DFill(segmentId,1.5)
        segmentationDisplayNode.SetSegmentOpacity2DOutline(segmentId,0.2)
        segmentation.GetSegment(segmentId).SetColor(r,g,b)  # color should be set in segmentation node
        # Fill by thresholding
        logging.info('Thresholding.')
        segmentEditorWidget.setActiveEffectByName("Threshold")
        effect = segmentEditorWidget.activeEffect()
        if 'Emphysema' in segmentName:
            effect.setParameter("MinimumThreshold",str(bullMin))
            effect.setParameter("MaximumThreshold",str(bullMax))     
        if 'Ventilated' in segmentName:
            effect.setParameter("MinimumThreshold",str(ventMin))
            effect.setParameter("MaximumThreshold",str(ventMax))     
        if 'Infiltration' in segmentName:
            effect.setParameter("MinimumThreshold",str(infMin))
            effect.setParameter("MaximumThreshold",str(infMax))     
        if 'Collapsed' in segmentName:
            effect.setParameter("MinimumThreshold",str(collMin))
            effect.setParameter("MaximumThreshold",str(collMax))            
        if 'Vessels' in segmentName:
            effect.setParameter("MinimumThreshold",str(vessMin))
            effect.setParameter("MaximumThreshold",str(vessMax))            
        effect.self().onApply()
    
    logging.info('Creat left lung  segments ....')
    segmentEditorWidget.setMasterVolumeNode(leftMaskedVolume)
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(leftMaskedVolume)
    segmentEditorWidget.setSegmentationNode(segmentationNode)

    # Create segments by thresholding
    segmentsFromHounsfieldUnits = [
        ["Emphysema left", 0.0,0.0,0.0],
        ["Ventilated left", 0,0.5,1.0],
        ["Infiltration left", 1.0,0.5,0.0],
        ["Collapsed left", 1.0,0.0,1.0],
        ["Vessels", 1.0,0.0,0.0] ]

    #for segmentName, thresholdMin, thresholdMax, r, g, b in segmentsFromHounsfieldUnits:
        # Delete previous segments
        #logging.info('Deleting segment.')
        #segmentId = segmentation.GetSegmentIdBySegmentName(segmentName)
        #segmentation.RemoveSegment(segmentId)
        
    for segmentName, r, g, b in segmentsFromHounsfieldUnits:
        # Create segment
        logging.info('Creating segment.')
        addedSegmentID = segmentationNode.GetSegmentation().AddEmptySegment(segmentName)
        segmentEditorNode.SetSelectedSegmentID(addedSegmentID)
        # Set color
        #logging.info('Setting segment color.')
        segmentId = segmentation.GetSegmentIdBySegmentName(segmentName)
        segmentationDisplayNode.SetSegmentOpacity3D(segmentId,0.2)
        #segmentationDisplayNode.SetSegmentOpacity(segmentId,1.)
        segmentationDisplayNode.SetSegmentOpacity2DFill(segmentId,1.5)
        segmentationDisplayNode.SetSegmentOpacity2DOutline(segmentId,0.2)
        segmentation.GetSegment(segmentId).SetColor(r,g,b)  # color should be set in segmentation node
        # Fill by thresholding
        logging.info('Thresholding.')
        segmentEditorWidget.setActiveEffectByName("Threshold")
        effect = segmentEditorWidget.activeEffect()
        if 'Emphysema' in segmentName:
            effect.setParameter("MinimumThreshold",str(bullMin))
            effect.setParameter("MaximumThreshold",str(bullMax))     
        if 'Ventilated' in segmentName:
            effect.setParameter("MinimumThreshold",str(ventMin))
            effect.setParameter("MaximumThreshold",str(ventMax))     
        if 'Infiltration' in segmentName:
            effect.setParameter("MinimumThreshold",str(infMin))
            effect.setParameter("MaximumThreshold",str(infMax))     
        if 'Collapsed' in segmentName:
            effect.setParameter("MinimumThreshold",str(collMin))
            effect.setParameter("MaximumThreshold",str(collMax))            
        if 'Vessels' in segmentName:
            effect.setParameter("MinimumThreshold",str(vessMin))
            effect.setParameter("MaximumThreshold",str(vessMax))            
        effect.self().onApply()
    
    

    # Delete temporary segment editor
    segmentEditorWidget.setMasterVolumeNode(inputVolume)
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(inputVolume)
    segmentEditorWidget = None
    slicer.mrmlScene.RemoveNode(segmentEditorNode)

   # Delete existing model storage nodes so that they will be recreated with default settings
    if delprev_cb: 
        existingTableNodes = slicer.util.getNodesByClass('vtkMRMLTableNode')
        for TableNode in existingTableNodes:
            slicer.mrmlScene.RemoveNode(TableNode)

    logging.info('Create Tables ....')        
    # Compute segment volumes
    resultsTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode')
    import SegmentStatistics
    segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
    segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
    segStatLogic.getParameterNode().SetParameter("ScalarVolume", masterVolumeNode.GetID())
    

    if genstat_cb: 
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled","True")
    else:
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled","False")
    segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.voxel_count.enabled","False")
    segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.volume_mm3.enabled","False")
    segStatLogic.computeStatistics()
    segStatLogic.exportToTable(resultsTableNode)

    minThrCol = vtk.vtkFloatArray()
    minThrCol.SetName("MinThr")
    minThrCol.InsertNextValue(bullMin) #right lung
    minThrCol.InsertNextValue(ventMin)
    minThrCol.InsertNextValue(infMin)
    minThrCol.InsertNextValue(collMin)
    minThrCol.InsertNextValue(vessMin)
    minThrCol.InsertNextValue(bullMin) #left lung
    minThrCol.InsertNextValue(ventMin)
    minThrCol.InsertNextValue(infMin)
    minThrCol.InsertNextValue(collMin)
    minThrCol.InsertNextValue(vessMin)

    maxThrCol = vtk.vtkFloatArray()
    maxThrCol.SetName("MaxThr")
    maxThrCol.InsertNextValue(bullMax) #right lung
    maxThrCol.InsertNextValue(ventMax)
    maxThrCol.InsertNextValue(infMax)
    maxThrCol.InsertNextValue(collMax)
    maxThrCol.InsertNextValue(vessMax)
    maxThrCol.InsertNextValue(bullMax) #left lung
    maxThrCol.InsertNextValue(ventMax)
    maxThrCol.InsertNextValue(infMax)
    maxThrCol.InsertNextValue(collMax)
    maxThrCol.InsertNextValue(vessMax)
    
    column = resultsTableNode.AddColumn(minThrCol)
    column = resultsTableNode.AddColumn(maxThrCol)

    segStatLogic.showTable(resultsTableNode)
    
    # Add a new column
    # Compute segment volumes
    
    _bulRightLung = round(float(resultsTableNode.GetCellText(0,3)))
    _venRightLung = round(float(resultsTableNode.GetCellText(1,3)))
    _infRightLung = round(float(resultsTableNode.GetCellText(2,3)))
    _colRightLung = round(float(resultsTableNode.GetCellText(3,3)))
    _vesRightLung = round(float(resultsTableNode.GetCellText(4,3)))
    _bulLeftLung = round(float(resultsTableNode.GetCellText(5,3)))
    _venLeftLung = round(float(resultsTableNode.GetCellText(6,3)))
    _infLeftLung = round(float(resultsTableNode.GetCellText(7,3)))
    _colLeftLung = round(float(resultsTableNode.GetCellText(8,3)))
    _vesLeftLung = round(float(resultsTableNode.GetCellText(9,3)))
    
    _rightLungVolume = _bulRightLung + _venRightLung + _infRightLung + _colRightLung - _vesRightLung
    _leftLungVolume = _bulLeftLung + _venLeftLung + _infLeftLung + _colLeftLung - _vesLeftLung
    _totalLungVolume = _rightLungVolume + _leftLungVolume
    
    _functionalRightVolume = _venRightLung
    _functionalLeftVolume = _venLeftLung
    _functionalTotalVolume = _venRightLung + _venLeftLung

    _affectedRightVolume = _infRightLung + _colRightLung + _bulRightLung
    _affectedLeftVolume = _infLeftLung + _colLeftLung + _bulLeftLung
    _affectedTotalVolume = _infRightLung + _colRightLung + _infLeftLung + _colLeftLung + _bulRightLung+ _bulLeftLung
    
    _rightLungVolumePerc = round(_rightLungVolume * 100. / _totalLungVolume)
    _leftLungVolumePerc = round(_leftLungVolume * 100. / _totalLungVolume)
    _totalLungVolumePerc = 100.
    
    _functionalRightVolumePerc = round(_functionalRightVolume * 100. / _rightLungVolume)
    _functionalLeftVolumePerc = round(_functionalLeftVolume * 100. / _leftLungVolume)
    _functionalTotalVolumePerc = round(_functionalTotalVolume * 100. / _totalLungVolume)

    _affectedRightVolumePerc = round(_affectedRightVolume * 100. / _rightLungVolume)
    _affectedLeftVolumePerc = round(_affectedLeftVolume * 100. / _leftLungVolume)
    _affectedTotalVolumePerc = round(_affectedTotalVolume * 100. / _totalLungVolume)
    
    
    _CovidQ = round(_affectedTotalVolume / _totalLungVolume,2)  
    
    
    
    if inccov_cb: 
        covidTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode')
        resTableNode = covidTableNode 
        
        
        column = resTableNode.AddColumn()
        column.SetName("Results")
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        resTableNode.AddEmptyRow()
        col=0
        resTableNode.SetCellText(0,col,"Right lung volume")
        resTableNode.SetCellText(1,col,"Left lung volume")
        resTableNode.SetCellText(2,col,"Total lung volume")
        resTableNode.SetCellText(4,col,"Functional right volume")
        resTableNode.SetCellText(5,col,"Functional left volume")
        resTableNode.SetCellText(6,col,"Functional total volume")
        resTableNode.SetCellText(8,col,"Affected right volume")
        resTableNode.SetCellText(9,col,"Affected left volume")
        resTableNode.SetCellText(10,col,"Affected total volume")
        resTableNode.SetCellText(12,col,"CovidQ (affected / functional)")
        column2 = resTableNode.AddColumn()
        column2.SetName("ml")
        #covidTableNode.SetCellText(1,1,"Test")
        col=1
        resTableNode.SetCellText(0,col,str(_rightLungVolume))
        resTableNode.SetCellText(1,col,str(_leftLungVolume))
        resTableNode.SetCellText(2,col,str(_totalLungVolume))
        resTableNode.SetCellText(4,col,str(_functionalRightVolume))
        resTableNode.SetCellText(5,col,str(_functionalLeftVolume))
        resTableNode.SetCellText(6,col,str(_functionalTotalVolume))
        resTableNode.SetCellText(8,col,str(_affectedRightVolume))
        resTableNode.SetCellText(9,col,str(_affectedLeftVolume))
        resTableNode.SetCellText(10,col,str(_affectedTotalVolume))
        resTableNode.SetCellText(12,col,str(_CovidQ))
        
        
        column3 = resTableNode.AddColumn()
        column3.SetName("%")
        col=2
        resTableNode.SetCellText(0,col,str(_rightLungVolumePerc))
        resTableNode.SetCellText(1,col,str(_leftLungVolumePerc))
        resTableNode.SetCellText(2,col,str(_totalLungVolumePerc))
        resTableNode.SetCellText(4,col,str(_functionalRightVolumePerc))
        resTableNode.SetCellText(5,col,str(_functionalLeftVolumePerc))
        resTableNode.SetCellText(6,col,str(_functionalTotalVolumePerc))
        resTableNode.SetCellText(8,col,str(_affectedRightVolumePerc))
        resTableNode.SetCellText(9,col,str(_affectedLeftVolumePerc))
        resTableNode.SetCellText(10,col,str(_affectedTotalVolumePerc))
     
        resTableNode.Modified();

        currentLayout = slicer.app.layoutManager().layout
        layoutWithTable = slicer.modules.tables.logic().GetLayoutWithTable(currentLayout)
        slicer.app.layoutManager().setLayout(layoutWithTable)
        slicer.app.applicationLogic().GetSelectionNode().SetActiveTableID(resTableNode.GetID())
        slicer.app.applicationLogic().PropagateTableSelection()
    
    # center viewports
    slicer.app.applicationLogic().FitSliceToAll()
    # center 3D view
    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.threeDWidget(0)
    threeDView = threeDWidget.threeDView()
    threeDView.resetFocalPoint()
    # bug workaround
    slicer.mrmlScene.RemoveNode(slicer.mrmlScene.GetFirstNodeByName('False lung masked volume'))
    # ensure user sees the new segments
    segmentationDisplayNode.Visibility2DOn()
    if show3D_cb: 
        # create 3D 
        segmentationNode.CreateClosedSurfaceRepresentation()
    
    stopTime = time.time()
    logging.info('Processing completed in {0:.2f} seconds'.format(stopTime-startTime))
#
# CTLungAnalyzerTest
#

class CTLungAnalyzerTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear()

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_CTLungAnalyzer1()

  def test_CTLungAnalyzer1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")

    # Get/create input data

    import SampleData
    registerSampleData()
    inputVolume = SampleData.downloadSample('DemoChestCT')
    self.delayDisplay('Loaded demo chest CT.')
    lungMaskSegmentation = SampleData.downloadSample('DemoLungMasks')
    self.delayDisplay('Loaded demo lung masks.')


    #outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")

    # Test the module logic

    logic = CTLungAnalyzerLogic()

    # Test algorithm with non-inverted threshold
    
    self.delayDisplay('Processing starts.')
    logic.process(inputVolume,
      lungMaskSegmentation,
      lungMaskSegmentation,
      lungMaskSegmentation.GetSegmentation().GetSegmentIdBySegmentName("Right Lung Mask"),
      lungMaskSegmentation.GetSegmentation().GetSegmentIdBySegmentName("Left Lung Mask"),
      -1000.,
      -950.,
      -950.,
      -750.,
      -750.,
      -400.,
      -400.,
      400.,
      400.,
      1000.,
      True,  # gen stat
      True,  # delete prev seg
      False, # COVID 
      False) # 3D
 
    self.delayDisplay('Processing ends.')

    self.delayDisplay('Test passed')