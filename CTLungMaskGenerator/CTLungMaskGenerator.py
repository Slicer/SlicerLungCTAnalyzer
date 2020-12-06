import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# CTLungMaskGenerator
#

class CTLungMaskGenerator(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Lung CT Mask Generator"  # TODO: make this more human readable by adding spaces
    self.parent.categories = ["Chest Imaging Platform"]  # TODO: set categories (folders where the module shows up in the module selector)
    self.parent.dependencies = []  # TODO: add here list of module names that this module requires
    self.parent.contributors = ["Rudolf Bumm (KSGR Switzerland)"]  # TODO: replace with "Firstname Lastname (Organization)"
    # TODO: update with short description of the module and a link to online module documentation
    self.parent.helpText = """
This is a 3D Slicer script that segments a right and a left lung mask from a given CT dataset. 
See more information in <a href="https://github.com/rbumm/projectname#SlicerCTLungMaskGenerator">module documentation</a>.
"""
    # TODO: replace with organization, grant and thanks
    self.parent.acknowledgementText = """
This file was originally developed by Rudolf Bumm, Kantonsspital Graubünden, Switzerland. """

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


#
# CTLungMaskGeneratorWidget
#

class CTLungMaskGeneratorWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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
    self._rightlungdefined = False
    self._leftlungdefined = False
    self._tracheadefined = False
    self._bifurcationdefined = False

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer).
    # Additional widgets can be instantiated manually and added to self.layout.
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/CTLungMaskGenerator.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)
    

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = CTLungMaskGeneratorLogic()

    # Connections

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    self.ui.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.markerRightLung.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.markerLeftLung.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.markerTrachea.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

    # Buttons
    self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.ui.resetButton.connect('clicked(bool)', self.onResetButton)
    self.ui.toggleSegmentsButton.connect('clicked(bool)', self.ontoggleSegmentsButton)


    logging.info('Delete clutter segments ....')
    allSegmentNodes = slicer.util.getNodes('vtkMRMLSegmentationNode*').values()
    for ctn in allSegmentNodes:
      #logging.info('Name:>' + ctn.GetName()+'<')
      teststr = ctn.GetName()
      if 'MaskSegmentation' in teststr:
        #logging.info('Found:' + ctn.GetName())
        slicer.mrmlScene.RemoveNode(ctn)
            #break        

    self.ui.cb_keepMarkers.enabled = False; 
    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()

    # Initialize the necessary markers 
    self.initializeMarkerNodes()


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

 
  def initializeMarkerNodes(self):

    # Temporary markups node

    if self.ui.cb_keepMarkers.checked == True: 
        # do not initialize nodes
        logging.info('Markers not touched.')
    else: 
        logging.info('Delete temporary markers ....')
        allSegmentNodes = slicer.util.getNodes('vtkMRMLMarkupsFiducialNode*').values()
        for ctn in allSegmentNodes:
          #logging.info('Name:>' + ctn.GetName()+'<')
          teststr = ctn.GetName()
          if '_marker' in teststr:
            #logging.info('Found:' + ctn.GetName())
            slicer.mrmlScene.RemoveNode(ctn)
                #break        
        def placementModeRightLungChanged(active):
          # Update buttons states and tooltips
          self._rightlungdefined = True
          if self._parameterNode.GetNodeReference("InputVolume") and self._rightlungdefined and self._leftlungdefined and self._tracheadefined:
            self.ui.applyButton.toolTip = "Compute output volume"
            self.ui.applyButton.enabled = True
          else:
            self.ui.applyButton.toolTip = "Select input volume node and all four region markers"
            self.ui.applyButton.enabled = False
          # You can inspect what is in the markups node here, delete the temporary markup node, etc.
        def placementModeLeftLungChanged(active):
          print("Placement: " +("active" if active else "inactive"))
          self._leftlungdefined = True
          # Update buttons states and tooltips
          if self._parameterNode.GetNodeReference("InputVolume") and self._rightlungdefined and self._leftlungdefined and self._tracheadefined:
            self.ui.applyButton.toolTip = "Compute output volume"
            self.ui.applyButton.enabled = True
          else:
            self.ui.applyButton.toolTip = "Select input volume node and all four region markers"
            self.ui.applyButton.enabled = False
          # You can inspect what is in the markups node here, delete the temporary markup node, etc.
        def placementModeTracheaChanged(active):
          print("Placement: " +("active" if active else "inactive"))
          # Update buttons states and tooltips
          self._tracheadefined = True
          if self._parameterNode.GetNodeReference("InputVolume") and self._rightlungdefined and self._leftlungdefined and self._tracheadefined:
            self.ui.applyButton.toolTip = "Compute output volume"
            self.ui.applyButton.enabled = True
          else:
            self.ui.applyButton.toolTip = "Select input volume node and all four region markers"
            self.ui.applyButton.enabled = False
          # You can inspect what is in the markups node here, delete the temporary markup node, etc.

        self.ui.markerRightLung.enabled = True; 
        self.ui.markerLeftLung.enabled = True; 
        self.ui.markerTrachea.enabled = True; 
        self.ui.cb_keepMarkers.enabled = True; 
        # Create and set up widget that contains a single "place markup" button. The widget can be placed in the module GUI.
        markupsRightLungNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsRightLungNode.SetName("_markerRL")
        placeWidget = slicer.qSlicerMarkupsPlaceWidget()
        placeWidget = self.ui.markerRightLung
        placeWidget.setMRMLScene(slicer.mrmlScene)
        placeWidget.setCurrentNode(markupsRightLungNode)
        placeWidget.buttonsVisible=False
        placeWidget.placeButton().show()
        placeWidget.connect('activeMarkupsFiducialPlaceModeChanged(bool)', placementModeRightLungChanged)
        #placeWidget.show()

        # Create and set up widget that contains a single "place markup" button. The widget can be placed in the module GUI.
        markupsLeftLungNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsLeftLungNode.SetName("_markerLL")
        placeWidget = slicer.qSlicerMarkupsPlaceWidget()
        placeWidget = self.ui.markerLeftLung
        placeWidget.setMRMLScene(slicer.mrmlScene)
        placeWidget.setCurrentNode(markupsLeftLungNode)
        placeWidget.buttonsVisible=False
        placeWidget.placeButton().show()
        placeWidget.connect('activeMarkupsFiducialPlaceModeChanged(bool)', placementModeLeftLungChanged)
        #placeWidget.show()

        # Create and set up widget that contains a single "place markup" button. The widget can be placed in the module GUI.
        markupsTracheaNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsTracheaNode.SetName("_markerT")
        placeWidget = slicer.qSlicerMarkupsPlaceWidget()
        placeWidget = self.ui.markerTrachea
        placeWidget.setMRMLScene(slicer.mrmlScene)
        placeWidget.setCurrentNode(markupsTracheaNode)
        placeWidget.buttonsVisible=False
        placeWidget.placeButton().show()
        placeWidget.connect('activeMarkupsFiducialPlaceModeChanged(bool)', placementModeTracheaChanged)
        #placeWidget.show()



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
    self.ui.inputSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputVolume"))

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

    self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputSelector.currentNodeID)
  
    self._parameterNode.EndModify(wasModified)

  def ontoggleSegmentsButton(self):
    """
    Toggle segments button.
    """
    segmentationNode = slicer.util.getNode('MaskSegmentation')
    segmentationDisplayNode = segmentationNode.GetDisplayNode()
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
      self.logic.process(self.ui.inputSelector.currentNode(), self.ui.ThresholdRangeWidget.minimumValue,self.ui.ThresholdRangeWidget.maximumValue)
      # enable checkbox keep Markers if user wants to do the algo again
      self.ui.cb_keepMarkers.enabled = True; 
    except Exception as e:
      slicer.util.errorDisplay("Failed to compute results: "+str(e))
      import traceback
      traceback.print_exc()

  def onResetButton(self):
    """
    Run processing when user clicks "Reset" button.
    """
    logging.info('Delete clutter segments ....')
    allSegmentNodes = slicer.util.getNodes('vtkMRMLSegmentationNode*').values()
    for ctn in allSegmentNodes:
      #logging.info('Name:>' + ctn.GetName()+'<')
      teststr = ctn.GetName()
      if 'MaskSegmentation' in teststr:
        #logging.info('Found:' + ctn.GetName())
        slicer.mrmlScene.RemoveNode(ctn)
            #break        
    # Initialize the necessary markers 
    self.initializeMarkerNodes()

 

#
# CTLungMaskGeneratorLogic
#

class CTLungMaskGeneratorLogic(ScriptedLoadableModuleLogic):
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
    ScriptedLoadableModuleLogic.__init__(self)

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    if not parameterNode.GetParameter("Threshold"):
      parameterNode.SetParameter("Threshold", "100.0")
    if not parameterNode.GetParameter("Invert"):
      parameterNode.SetParameter("Invert", "false")
  
  def rasToDisplay(self, r, a, s):
    displayCoords = [0, 0, 0, 1]

    # get the slice node
    lm = slicer.app.layoutManager()
    sliceWidget = lm.sliceWidget('Red')
    sliceLogic = sliceWidget.sliceLogic()
    sliceNode = sliceLogic.GetSliceNode()

    xyToRASMatrix = sliceNode.GetXYToRAS()
    rasToXyMatrix = vtk.vtkMatrix4x4()
    rasToXyMatrix.Invert(xyToRASMatrix, rasToXyMatrix)

    worldCoords = [r, a, s, 1.0]
    rasToXyMatrix.MultiplyPoint(worldCoords, displayCoords)

    return (int(displayCoords[0]), int(displayCoords[1]))

  def process(self, inputVolume, minThreshold, maxThreshold, show3D_cb=True, showResult=True):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param inputVolume: volume to be thresholded
    :param outputVolume: thresholding result
    :param imageThreshold: values above/below this threshold will be set to 0
    :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
    :param showResult: show output volume in slice viewers
    """
    logging.info('Processing started.')


    if not inputVolume:
      raise ValueError("Input volume is invalid")
    logging.info('Input present.')

    import time
    startTime = time.time()


    # Compute 
    # Resample the volume to 0.25mm spacing
    logging.info('Resampling volume, please wait ... ')
    resampledVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Resampled Volume")
    parameters = {"outputPixelSpacing":"2.0,2.0,2.0", "InputVolume":inputVolume,"interpolationType":'linear',"OutputVolume":resampledVolume}
    slicer.cli.runSync(slicer.modules.resamplescalarvolume, None, parameters)
    masterVolumeNode = resampledVolume
    
    #fidList = slicer.util.getNode('F')

    fidListRightLung = slicer.util.getNode('_markerRL')
    fidListLeftLung = slicer.util.getNode('_markerLL')
    fidListTrachea = slicer.util.getNode('_markerT')
    #numFids = fidList.GetNumberOfFiducials()
    #for i in range(numFids):
    #    ras = [0,0,0]
    #    fidList.GetNthFiducialPosition(i,ras)
    #    # the world position is the RAS position with any transform matrices applied
    #    world = [0,0,0,0]
    #    fidList.GetNthFiducialWorldCoordinates(0,world)
    #    print(i,": RAS =",ras,", world =",world)


    # Get voxel position in IJK coordinate system
    max = 0
    min = 0
    
    logging.info('Analyzing volume, please wait ... ')
    import numpy as np
    volumeArray = slicer.util.arrayFromVolume(masterVolumeNode)
    # Get position of highest voxel value
    point_Kji = np.where(volumeArray == volumeArray.max())
    point_Ijk = [point_Kji[2][0], point_Kji[1][0], point_Kji[0][0]]
    max = volumeArray.max()
    min = volumeArray.min()
    
    #print("Min: " + str(min))
    #print("Max: " + str(max))
    #indices = np.where(volumeArray>-3000)
    #numberOfVoxels = len(indices[0])
    #print(numberOfVoxels)
    #max = 0
    #min = 0
    #for pointIndex in range(numberOfVoxels):
    #    i = indices[0][pointIndex]
    #    j = indices[1][pointIndex]
    #    k = indices[2][pointIndex]
    #    if min > volumeArray[i,j,k]: 
    #        min = volumeArray[i,j,k]
    #    if max < volumeArray[i,j,k]: 
    #        max = volumeArray[i,j,k]
        # print("%d %d %d %d" % (i, j, k, volumeArray[i,j,k]))
    #print("Min: " + str(min))
    #print("Max: " + str(max))


    # Get physical coordinates from voxel coordinates
    volumeIjkToRas = vtk.vtkMatrix4x4()
    masterVolumeNode.GetIJKToRASMatrix(volumeIjkToRas)
    point_VolumeRas = [0, 0, 0, 1]
    volumeIjkToRas.MultiplyPoint(np.append(point_Ijk,1.0), point_VolumeRas)

    # If volume node is transformed, apply that transform to get volume's RAS coordinates
    transformVolumeRasToRas = vtk.vtkGeneralTransform()
    slicer.vtkMRMLTransformNode.GetTransformBetweenNodes(masterVolumeNode.GetParentTransformNode(), None, transformVolumeRasToRas)
    point_Ras = transformVolumeRasToRas.TransformPoint(point_VolumeRas[0:3])

    # Add a markup at the computed position and print its coordinates
    # markupsNode.AddFiducial(point_Ras[0], point_Ras[1], point_Ras[2], "max")
    # print(point_Ras)


    logging.info('Delete clutter segments ....')
    allSegmentNodes = slicer.util.getNodes('vtkMRMLSegmentationNode*').values()
    for ctn in allSegmentNodes:
      #logging.info('Name:>' + ctn.GetName()+'<')
      teststr = ctn.GetName()
      if 'MaskSegmentation' in teststr:
        #logging.info('Found:' + ctn.GetName())
        slicer.mrmlScene.RemoveNode(ctn)
            #break        


    # Create segmentation
    logging.info('Create segmentation ... ')
    segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    segmentationNode.SetName("MaskSegmentation")
    segmentationNode.CreateDefaultDisplayNodes() # only needed for display
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(masterVolumeNode)
    segmentationDisplayNode=segmentationNode.GetDisplayNode()

    # Create temporary segment editor to get access to effects
    logging.info('Create temporary segment editor ... ')
    segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
    segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
    segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
    segmentEditorWidget.setSegmentationNode(segmentationNode)
    segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)
    lm = slicer.app.layoutManager()
    sliceWidget = lm.sliceWidget('Red')

    if not segmentEditorWidget.effectByName("Mask volume"):
        slicer.util.errorDisplay("Please install 'SegmentEditorExtraEffects' extension using Extension Manager.")
    #if not segmentEditorWidget.effectByName("Wrap Solidify"):
    #    slicer.util.errorDisplay("Please install 'SurfaceWrapSolidify' extension using Extension Manager.")


    
    # Create segments by thresholding
    logging.info('Create lung segments  ... ')
    
    # Create segment
    segmentEditorNode.SetMasterVolumeIntensityMask(True)
    segmentEditorNode.SetMasterVolumeIntensityMaskRange(min, maxThreshold)
    #addedSegmentID = segmentationNode.GetSegmentation().AddEmptySegment(segmentName)
    #segmentEditorNode.SetSelectedSegmentID(addedSegmentID)
    
    logging.info('Creating seeds ... ')
    # Create right lung seed segment 
    append = vtk.vtkAppendPolyData()
    numFids = fidListRightLung.GetNumberOfFiducials()
    for i in range(numFids):
      ras = [0,0,0]
      fidListRightLung.GetNthFiducialPosition(i,ras)
      rightlungSeed = vtk.vtkSphereSource()
      rightlungSeed.SetCenter(ras)
      rightlungSeed.SetRadius(10)
      rightlungSeed.Update()
      append.AddInputData(rightlungSeed.GetOutput())

    append.Update()
    color = (128, 174, 128)
    color = np.array(color, float) / 255
    rightLungSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(append.GetOutput(), "Right lung mask", color)
    
    # Create left lung seed segment 
    append = vtk.vtkAppendPolyData()
    numFids = fidListLeftLung.GetNumberOfFiducials()
    for i in range(numFids):
      ras = [0,0,0]
      fidListLeftLung.GetNthFiducialPosition(i,ras)
      leftlungSeed = vtk.vtkSphereSource()
      leftlungSeed.SetCenter(ras)
      leftlungSeed.SetRadius(10)
      leftlungSeed.Update()
      append.AddInputData(leftlungSeed.GetOutput())

    append.Update()
    color = (241, 214, 145)
    color = np.array(color, float) / 255
    leftLungSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(append.GetOutput(), "Left lung mask", color)

    # Create trachea seed segment 
    append = vtk.vtkAppendPolyData()
    numFids = fidListTrachea.GetNumberOfFiducials()
    for i in range(numFids):
      ras = [0,0,0]
      fidListTrachea.GetNthFiducialPosition(i,ras)
      tracheaSeed = vtk.vtkSphereSource()
      tracheaSeed.SetCenter(ras)
      tracheaSeed.SetRadius(2)
      tracheaSeed.Update()
      append.AddInputData(tracheaSeed.GetOutput())

    append.Update()
    color = (182, 228,255)
    color = np.array(color, float) / 255
    tracheaSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(append.GetOutput(), "Trachea mask", color)
    
    # Run segmentation
    logging.info('Run growing from seeds segmentation ... ')
    segmentEditorWidget.setActiveEffectByName("Grow from seeds")
    effect = segmentEditorWidget.activeEffect()
    effect.self().onPreview()
    effect.self().onApply()
    
    segmentEditorNode.SetSelectedSegmentID("Right lung mask")

    segmentEditorNode.SetMasterVolumeIntensityMask(False)
    #otherwise vessels do not fill

    #close holes
    logging.info('Closing holes in segmentations ... ')
    do_smooth = True
    if do_smooth: 
        segmentEditorWidget.setActiveEffectByName("Smoothing")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("SmoothingMethod","MORPHOLOGICAL_CLOSING")
        effect.setParameter("KernelSizeMm","12")
        effect.self().onApply()
    #close holes
    logging.info('Smoothing external surface ... ')
    do_smooth = True
    if do_smooth: 
        segmentEditorWidget.setActiveEffectByName("Smoothing")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("SmoothingMethod","GAUSSIAN")
        effect.setParameter("KernelSizeMm","2")
        effect.self().onApply()

            
    segmentEditorNode.SetSelectedSegmentID("Left lung mask")

    segmentEditorNode.SetMasterVolumeIntensityMask(False)
    #otherwise vessels do not fill

    #close holes
    logging.info('Closing holes in segmentations ... ')
    do_smooth = True
    if do_smooth: 
        segmentEditorWidget.setActiveEffectByName("Smoothing")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("SmoothingMethod","MORPHOLOGICAL_CLOSING")
        effect.setParameter("KernelSizeMm","12")
        effect.self().onApply()
    #close holes
    logging.info('Smoothing external surface ... ')
    do_smooth = True
    if do_smooth: 
        segmentEditorWidget.setActiveEffectByName("Smoothing")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("SmoothingMethod","GAUSSIAN")
        effect.setParameter("KernelSizeMm","2")
        effect.self().onApply()

#self.takeScreenshot('Lung CT Mask Generator','Left lung mask')
#print(slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentEditorNode"))

    # Delete temporary segment editor
    logging.info('Deleting temporary segment editor ... ')
    segmentEditorWidget = None
    slicer.mrmlScene.RemoveNode(segmentEditorNode)    

    # Delete resampled Volume 
    logging.info('Deleting resampled volume node ... ')
    slicer.mrmlScene.RemoveNode(resampledVolume)

    # Delete existing model storage nodes so that they will be recreated with default settings
    logging.info('Delete table nodes ... ')
    existingTableNodes = slicer.util.getNodesByClass('vtkMRMLTableNode')
    for TableNode in existingTableNodes:
        teststr = TableNode.GetName()
        if '_maskRes' in teststr:
            #logging.info('Found:' + ctn.GetName())
            slicer.mrmlScene.RemoveNode(TableNode)
            #break        
    # Compute segment volumes
    resultsTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode')
    import SegmentStatistics
    segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
    segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
    segStatLogic.getParameterNode().SetParameter("ScalarVolume", masterVolumeNode.GetID())
    segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled","False")
    segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.voxel_count.enabled","False")
    segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.volume_mm3.enabled","False")
    segStatLogic.computeStatistics()
    segStatLogic.exportToTable(resultsTableNode)
    #segStatLogic.showTable(resultsTableNode)
    resultsTableNode.SetName("_maskResultsTable")

    # center viewports
    slicer.app.applicationLogic().FitSliceToAll()
    # center 3D view
    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.threeDWidget(0)
    threeDView = threeDWidget.threeDView()
    threeDView.resetFocalPoint()
    # ensure user sees the new segments
    segmentationDisplayNode.Visibility2DOn()
    if show3D_cb: 
        # create 3D 
        segmentationNode.CreateClosedSurfaceRepresentation()

    # clear up
  

#
# CTLungMaskGeneratorTest
#

class CTLungMaskGeneratorTest(ScriptedLoadableModuleTest):
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
    self.test_CTLungMaskGenerator1()

  def test_CTLungMaskGenerator1(self):
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
    inputVolume = SampleData.downloadSample('CTChest')
    self.delayDisplay('Loaded test data set')

    logging.info('Delete clutter markers ....')
    allSegmentNodes = slicer.util.getNodes('vtkMRMLMarkupsFiducialNode*').values()
    for ctn in allSegmentNodes:
        #logging.info('Name:>' + ctn.GetName()+'<')
        teststr = ctn.GetName()
        if '_marker' in teststr:
        #logging.info('Found:' + ctn.GetName())
            slicer.mrmlScene.RemoveNode(ctn)
            #break        
    # Create new markers
    markupsRightLungNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
    markupsRightLungNode.SetName("_markerRightLung")
    markupsLeftLungNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
    markupsLeftLungNode.SetName("_markerLeftLung")
    markupsTracheaNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
    markupsTracheaNode.SetName("_markerUpperTrachea")
    markupsBifurcationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
    markupsBifurcationNode.SetName("_markerBifurcation")

    # add one fiducial each
    markupsRightLungNode.CreateDefaultDisplayNodes()
    markupsRightLungNode.AddFiducial(64.,43.,-170.)
    markupsLeftLungNode.CreateDefaultDisplayNodes()
    markupsLeftLungNode.AddFiducial(-95.,25.,-170.)
    markupsTracheaNode.CreateDefaultDisplayNodes()
    markupsTracheaNode.AddFiducial(-8.7,15.7,-12.8)
    markupsBifurcationNode.CreateDefaultDisplayNodes()
    markupsBifurcationNode.AddFiducial(-12.4,-24.3,-117.8)

    # Test the module logic

    logic = CTLungMaskGeneratorLogic()

    # Test algorithm without 3D
    self.delayDisplay("Processing, please wait ...")

    logic.process(inputVolume, -1000.,-200.,False)

    resultsTableNode = slicer.util.getNode('_maskResultsTable')
    _volumeRightLungMask = round(float(resultsTableNode.GetCellText(0,1)))
    _volumeLeftLungMask = round(float(resultsTableNode.GetCellText(1,1)))
    print(_volumeRightLungMask)
    print(_volumeLeftLungMask)
    # assert vs known volumes of the chest CT dataset
    self.assertEqual(_volumeRightLungMask, 3272) 
    self.assertEqual(_volumeLeftLungMask, 3184)


    self.delayDisplay('Test passed')
