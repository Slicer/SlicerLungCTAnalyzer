import os
import sys
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

import SimpleITK as sitk
import sitkUtils

#
# LungCTSegmenter
#

class LungCTSegmenter(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Lung CT Segmenter"
    self.parent.categories = ["Chest Imaging Platform"]
    self.parent.dependencies = []
    self.parent.contributors = ["Rudolf Bumm (KSGR), Andras Lasso (PERK)"]
    self.parent.helpText = """
This module segments lungs and airways from chest CT either with a few user-defined landmarks or by involving AI. 
See more information in <a href="https://github.com/rbumm/SlicerLungCTAnalyzer">LungCTAnalyzer extension documentation</a>.<br>

"""
    self.parent.acknowledgementText = """
This extension was originally developed by Rudolf Bumm (KSKR) and Andras Lasso (PERK). 
<br><br>
AI segmentation involves
<br><br>
<a href="https://github.com/JoHof/lungmask">Lungmask U-net</a><br>See Hofmanninger, J., Prayer, F., Pan, J. et al. Automatic lung segmentation in routine imaging is primarily a data diversity problem, not a methodology problem. Eur Radiol Exp 4, 50 (2020). 
<a href="https://doi.org/10.1186/s41747-020-00173-2">https://doi.org/10.1186/s41747-020-00173-2</a>
<br><br>
and<br>
<br>
<a href="https://github.com/wasserth/TotalSegmentator">Totalsegmentator</a><br>See Wasserthal J., Meyer M., , Hanns-Christian Breit H.C., Cyriac J., Shan Y., Segeroth, M.: TotalSegmentator: robust segmentation of 104 anatomical structures in CT images. 
<a href="https://arxiv.org/abs/2208.05868">https://arxiv.org/abs/2208.05868</a>

"""

    # Sample data is already registered by LungCTAnalyzer module, so there is no need to add here

#
# LungCTSegmenterWidget
#

class LungCTSegmenterWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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
      self._rightLungFiducials = None
      self._leftLungFiducials = None
      self._tracheaFiducials = None
      self._updatingGUIFromParameterNode = False
      self.createDetailedAirways = False
      self.createVessels = False
      self.useAI = False
      self.fastOption = False
      self.shrinkMasks = False
      self.upgradeAI = False
      self.detailedMasks = False
      self.isSufficientNumberOfPointsPlaced = False
      self.saveFiducials = False
      self.inputVolume = None
      self.VolumeRenderingShift = 0
      self.volumeRenderingDisplayNode = None



  def setup(self):
      """
      Called when the user opens the module the first time and the widget is initialized.
      """
      ScriptedLoadableModuleWidget.setup(self)

      # Load widget from .ui file (created by Qt Designer).
      # Additional widgets can be instantiated manually and added to self.layout.
      uiWidget = slicer.util.loadUI(self.resourcePath('UI/LungCTSegmenter.ui'))
      self.layout.addWidget(uiWidget)
      self.ui = slicer.util.childWidgetVariables(uiWidget)

      # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
      # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
      # "setMRMLScene(vtkMRMLScene*)" slot.
      uiWidget.setMRMLScene(slicer.mrmlScene)

      # Create logic class. Logic implements all computations that should be possible to run
      # in batch mode, without a graphical user interface.
      self.logic = LungCTSegmenterLogic()

      for placeWidget in [self.ui.rightLungPlaceWidget, self.ui.leftLungPlaceWidget, self.ui.tracheaPlaceWidget]:
          placeWidget.buttonsVisible=False
          placeWidget.placeButton().show()
          placeWidget.deleteButton().show()

      # Populate comboboxes
      list = ["low detail", "medium detail", "high detail"]
      self.ui.detailLevelComboBox.addItems(list);

      list = ["lungmask R231", "lungmask LTRCLobes", "lungmask LTRCLobes_R231", "lungmask R231CovidWeb", "MONAILabel", "TotalSegmentator lung basic", "TotalSegmentator lung extended", "TotalSegmentator all"]
      self.ui.engineAIComboBox.addItems(list);

      # Connections

      # These connections ensure that we update parameter node when scene is closed
      self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
      self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

      # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
      # (in the selected parameter node).
      self.ui.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
      
      # Connect threshold range sliders 
      self.ui.LungThresholdRangeWidget.connect('valuesChanged(double,double)', self.onLungThresholdRangeWidgetChanged)
      self.ui.AirwayThresholdRangeWidget.connect('valuesChanged(double,double)', self.onAirwayThresholdRangeWidgetChanged)
      self.ui.VesselThresholdRangeWidget.connect('valuesChanged(double,double)', self.onVesselThresholdRangeWidgetChanged)

      # Connect double sliders 
      self.ui.VolumeRenderingShiftSliderWidget.connect('valueChanged(double)', self.onShiftSliderWidgetChanged)
      
      # Connect combo boxes 
      self.ui.detailLevelComboBox.currentTextChanged.connect(self.updateParameterNodeFromGUI)
      self.ui.engineAIComboBox.currentTextChanged.connect(self.updateParameterNodeFromGUI)
      
      # Connect check boxes 
      self.ui.detailedAirwaysCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
      self.ui.createVesselsCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
      self.ui.useAICheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
      self.ui.shrinkMasksCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
      self.ui.upgradeAICheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
      self.ui.detailedMasksCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
      self.ui.saveFiducialsCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
      self.ui.fastCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)

      # Buttons
      self.ui.startButton.connect('clicked(bool)', self.onStartButton)
      self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
      self.ui.cancelButton.connect('clicked(bool)', self.onCancelButton)
      self.ui.updateIntensityButton.connect('clicked(bool)', self.onUpdateIntensityButton)
      self.ui.setDefaultButton.connect('clicked(bool)', self.onSetDefaultButton)
      
      self.ui.toggleSegmentationVisibilityButton.connect('clicked(bool)', self.onToggleSegmentationVisibilityButton)
      self.ui.toggleVolumeRenderingVisibilityButton.connect('clicked(bool)', self.onToggleVolumeRenderingVisibilityButton)
      self.ui.engineAIComboBox.enabled = False
      # Make sure parameter node is initialized (needed for module reload)
      
      self.initializeParameterNode()
      slicer.app.applicationLogic().FitSliceToAll()

      # Initial GUI update
      self.updateGUIFromParameterNode()
      self.ui.toggleSegmentationVisibilityButton.enabled = False
      self.ui.toggleVolumeRenderingVisibilityButton.enabled = False
      self.ui.VolumeRenderingShiftSliderWidget.enabled = False

      self.ui.fastCheckBox.enabled = False


  def cleanup(self):
      """
      Called when the application closes and the module widget is destroyed.
      """
      self.removeFiducialObservers()
      self.removeObservers()
      # self.removeKeyboardShortcuts()
      self.logic = None

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
      # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
      self.removeFiducialObservers()

  def onSceneStartClose(self, caller, event):
      """
      Called just before the scene is closed.
      """
      # Parameter node will be reset, do not use it anymore
      self.setParameterNode(None)
      self.removeFiducialObservers()

  def removeFiducialObservers(self):
      self.updateFiducialObservations(self._rightLungFiducials, None)
      self.updateFiducialObservations(self._leftLungFiducials, None)
      self.updateFiducialObservations(self._tracheaFiducials, None)
      self._rightLungFiducials = None
      self._leftLungFiducials = None
      self._tracheaFiducials = None


  def onSetDefaultButton(self):
      self.ui.VolumeRenderingShiftSliderWidget.value = 0
      self.ui.LungThresholdRangeWidget.minimumValue = -1500
      self.ui.LungThresholdRangeWidget.maximumValue = -400
      self.ui.AirwayThresholdRangeWidget.minimumValue = -1500
      self.ui.AirwayThresholdRangeWidget.maximumValue = -850
      self.ui.VesselThresholdRangeWidget.minimumValue = -0
      self.ui.VesselThresholdRangeWidget.maximumValue = 3000
      self.updateParameterNodeFromGUI()

  def onShiftSliderWidgetChanged(self):
       self.updateParameterNodeFromGUI()
       self.updateVolumeRendering()
  def onLungThresholdRangeWidgetChanged(self):
       self.updateParameterNodeFromGUI()
      
  def onAirwayThresholdRangeWidgetChanged(self):
       self.updateParameterNodeFromGUI()

  def onVesselThresholdRangeWidgetChanged(self):
       self.updateParameterNodeFromGUI()

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
      
      self.logic = LungCTSegmenterLogic()
      self.setParameterNode(self.logic.getParameterNode())

      # Select default input nod#es if nothing is selected yet to save a few clicks for the user
      if not self.logic.inputVolume:
          firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
          if firstVolumeNode:
              self.logic.inputVolume = firstVolumeNode
              # Set lung CT window / level of inputVolume 
              displayNode = self.logic.inputVolume.GetDisplayNode()
              displayNode.AutoWindowLevelOff()
              displayNode.SetWindowLevel(1400, -500)
      #if not self.logic.outputSegmentation:
      #    firstSegmentationNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentationNode")
      #    if firstSegmentationNode:
      #        self.logic.outputSegmentation = firstSegmentationNode

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

  def setInstructions(self, text):
      #self.ui.instructionsLabel.text = f"<h1><b>{text}</b></h1>"
      self.ui.instructionsLabel.setHtml(f"<h1><b>{text}</b></h1>")
      slicer.app.processEvents()

  def setInstructionPlaceMorePoints(self, location, startingFrom, target, current):
      numberOfPointsToPlace = target - current
      plural = "s" if numberOfPointsToPlace > 1 else ""
      more = "more " if current > startingFrom else ""
      self.setInstructions(f"Place {numberOfPointsToPlace} {more} point{plural} in the {location}.")

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
      self.ui.inputVolumeSelector.setCurrentNode(self.logic.inputVolume)
      self.ui.outputSegmentationSelector.setCurrentNode(self.logic.outputSegmentation)

      self.ui.rightLungPlaceWidget.setCurrentNode(self.logic.rightLungFiducials)
      self.ui.leftLungPlaceWidget.setCurrentNode(self.logic.leftLungFiducials)
      self.ui.tracheaPlaceWidget.setCurrentNode(self.logic.tracheaFiducials)
      
      # Display instructions
      isSufficientNumberOfPointsPlaced = False
      if not self.logic.segmentationStarted or not self.logic.rightLungFiducials or not self.logic.leftLungFiducials or not self.logic.tracheaFiducials:
          # Segmentation has not started yet
          self.ui.adjustPointsGroupBox.enabled = False
          if not self.logic.inputVolume:
              self.setInstructions("Select input volume.")
          else:
              self.setInstructions('Click "Start" to initiate point placement.')
      else:
          slicer.app.processEvents()
          rightLungF = self.logic.rightLungFiducials.GetNumberOfDefinedControlPoints()
          leftLungF = self.logic.leftLungFiducials.GetNumberOfDefinedControlPoints()
          tracheaF = self.logic.tracheaFiducials.GetNumberOfDefinedControlPoints()
          #print(" R " + str(rightLungF) + " L " + str(leftLungF) + " T " + str(tracheaF))
          
          # Segmentation is in progress
          self.ui.adjustPointsGroupBox.enabled = True
          if  rightLungF < 3 and not self.useAI:
              self.setInstructionPlaceMorePoints("right lung", 0, 3, rightLungF)
              self.ui.rightLungPlaceWidget.placeModeEnabled = True
              slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView)
          elif leftLungF < 3 and not self.useAI:
              self.setInstructionPlaceMorePoints("left lung", 0, 3, leftLungF)
              self.ui.leftLungPlaceWidget.placeModeEnabled = True
              slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView)
          elif rightLungF < 6 and not self.useAI:
              self.setInstructionPlaceMorePoints("right lung", 3, 6, rightLungF)
              self.ui.rightLungPlaceWidget.placeModeEnabled = True
              slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpGreenSliceView)
          elif leftLungF < 6 and not self.useAI:
              self.setInstructionPlaceMorePoints("left lung", 3, 6, leftLungF)
              self.ui.leftLungPlaceWidget.placeModeEnabled = True
              slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpGreenSliceView)
          elif tracheaF < 1 and (not self.useAI or self.createDetailedAirways):
              self.setInstructionPlaceMorePoints("trachea", 0, 1, tracheaF)
              self.ui.tracheaPlaceWidget.placeModeEnabled = True
              slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpGreenSliceView)
          else:
              if self.useAI:
                  self.setInstructions('Click "Apply" to finalize.')
                  self.ui.tracheaPlaceWidget.placeModeEnabled = False
                  self.ui.adjustPointsGroupBox.enabled = True
              else:
                  self.setInstructions('Verify that segmentation is complete. Click "Apply" to finalize.')
              slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
              self.isSufficientNumberOfPointsPlaced = True

      self.ui.startButton.enabled = not self.logic.segmentationStarted
      self.ui.cancelButton.enabled = self.logic.segmentationStarted
      self.ui.updateIntensityButton.enabled = self.logic.segmentationStarted
      self.ui.applyButton.enabled = self.isSufficientNumberOfPointsPlaced
      if self.logic.segmentationFinished: 
        self.ui.applyButton.enabled = False
        self.ui.cancelButton.enabled = True
        self.ui.startButton.enabled = False
        
      self.ui.detailedAirwaysCheckBox.checked = self.createDetailedAirways
      self.ui.createVesselsCheckBox.checked = self.createVessels
      self.ui.useAICheckBox.checked = self.useAI
      self.ui.fastCheckBox.checked = self.fastOption
      
      self.ui.shrinkMasksCheckBox.checked = self.shrinkMasks
      self.ui.upgradeAICheckBox.checked = self.upgradeAI
      self.ui.detailedMasksCheckBox.checked = self.detailedMasks
      self.ui.saveFiducialsCheckBox.checked = self.saveFiducials
      self.ui.detailLevelComboBox.currentText = self.logic.airwaySegmentationDetailLevel
      self.ui.engineAIComboBox.currentText = self.logic.engineAI      
      self.ui.VolumeRenderingShiftSliderWidget.value = self.VolumeRenderingShift
      self.ui.LungThresholdRangeWidget.minimumValue = self.logic.lungThresholdMin
      self.ui.LungThresholdRangeWidget.maximumValue = self.logic.lungThresholdMax 
      self.ui.AirwayThresholdRangeWidget.minimumValue = self.logic.airwayThresholdMin
      self.ui.AirwayThresholdRangeWidget.maximumValue = self.logic.airwayThresholdMax       
      self.ui.VesselThresholdRangeWidget.minimumValue = self.logic.vesselThresholdMin
      self.ui.VesselThresholdRangeWidget.maximumValue = self.logic.vesselThresholdMax       

      self.updateFiducialObservations(self._rightLungFiducials, self.logic.rightLungFiducials)
      self.updateFiducialObservations(self._leftLungFiducials, self.logic.leftLungFiducials)
      self.updateFiducialObservations(self._tracheaFiducials, self.logic.tracheaFiducials)
      self._rightLungFiducials = self.logic.rightLungFiducials
      self._leftLungFiducials = self.logic.leftLungFiducials
      self._tracheaFiducials = self.logic.tracheaFiducials

      # All the GUI updates are done
      self._updatingGUIFromParameterNode = False
      

  def updateFiducialObservations(self, oldFiducial, newFiducial):
      if oldFiducial == newFiducial:
          return
      if oldFiducial:
          self.removeObserver(oldFiducial, slicer.vtkMRMLMarkupsNode.PointPositionDefinedEvent, self.updateSeeds)
          self.removeObserver(oldFiducial, slicer.vtkMRMLMarkupsNode.PointPositionUndefinedEvent, self.updateSeeds)
      if newFiducial:
          self.addObserver(newFiducial, slicer.vtkMRMLMarkupsNode.PointPositionDefinedEvent, self.updateSeeds)
          self.addObserver(newFiducial, slicer.vtkMRMLMarkupsNode.PointPositionUndefinedEvent, self.updateSeeds)

  def updateSeeds(self, caller, eventId):
      # Lock all fiducials - add/remove them instead of moving (if markup is moved then we would need to reinitialize
      # region growing, which would take time)
      slicer.modules.markups.logic().SetAllMarkupsLocked(caller, True)

      self.updateGUIFromParameterNode()
      if self.isSufficientNumberOfPointsPlaced: 
          self.logic.updateSegmentation()

  def updateParameterNodeFromGUI(self, caller=None, event=None):
      """
      This method is called when the user makes any change in the GUI.
      The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
      """

      if self._parameterNode is None or self.logic is None or self._updatingGUIFromParameterNode:
          return

      wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

      self.logic.inputVolume = self.ui.inputVolumeSelector.currentNode()
      self.logic.outputSegmentation = self.ui.outputSegmentationSelector.currentNode()
      self.VolumeRenderingShift = self.ui.VolumeRenderingShiftSliderWidget.value
      self.logic.lungThresholdMin = self.ui.LungThresholdRangeWidget.minimumValue
      self.logic.lungThresholdMax = self.ui.LungThresholdRangeWidget.maximumValue
      self.logic.airwayThresholdMin = self.ui.AirwayThresholdRangeWidget.minimumValue
      self.logic.airwayThresholdMax = self.ui.AirwayThresholdRangeWidget.maximumValue
      self.logic.vesselThresholdMin = self.ui.VesselThresholdRangeWidget.minimumValue
      self.logic.vesselThresholdMax = self.ui.VesselThresholdRangeWidget.maximumValue
      self.createDetailedAirways = self.ui.detailedAirwaysCheckBox.checked 
      self.createVessels = self.ui.createVesselsCheckBox.checked 
      self.useAI = self.ui.useAICheckBox.checked 
      self.fastOption = self.ui.fastCheckBox.checked 
      self.ui.engineAIComboBox.enabled = self.useAI
      self.shrinkMasks = self.ui.shrinkMasksCheckBox.checked 
      self.upgradeAI = self.ui.upgradeAICheckBox.checked 
      self.detailedMasks = self.ui.detailedMasksCheckBox.checked 
      self.saveFiducials = self.ui.saveFiducialsCheckBox.checked 
      self.logic.airwaySegmentationDetailLevel = self.ui.detailLevelComboBox.currentText
      self.logic.engineAI = self.ui.engineAIComboBox.currentText
      if self.logic.engineAI.find("TotalSegmentator") == 0:            
          self.ui.fastCheckBox.enabled = True
      else:
          self.ui.fastCheckBox.enabled = False

    
      self._parameterNode.EndModify(wasModified)

  def onToggleSegmentationVisibilityButton(self):
      """
      Toggle segmentation visibility.
      """
      segmentationNode = self.logic.outputSegmentation
      segmentationNode.CreateDefaultDisplayNodes()
      segmentationDisplayNode = segmentationNode.GetDisplayNode()
      if segmentationDisplayNode.GetVisibility2D():
          segmentationDisplayNode.Visibility2DOff()
          segmentationDisplayNode.Visibility3DOff()
      else:
          segmentationDisplayNode.Visibility2DOn()
          segmentationDisplayNode.Visibility3DOn()

  def updateVolumeRendering(self):
      """
      Update Volume rendering 
      """
      if not self.logic.maskedVolume: 
        self.logic.maskedVolume = slicer.mrmlScene.GetFirstNodeByName(self.logic.inputVolume.GetName() + f' masked volume')
        if not self.logic.maskedVolume:
            slicer.util.warningDisplay("No masked volume found.\n")
        return
      volRenLogic = slicer.modules.volumerendering.logic()
      self.volumeRenderingDisplayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(self.logic.maskedVolume)
      self.volumeRenderingDisplayNode.SetVisibility(True)
      self.volumeRenderingDisplayNode.GetVolumePropertyNode().Copy(volRenLogic.GetPresetByName("CT-Coronary-Arteries-3")) 
      volRenWidget = slicer.modules.volumerendering.widgetRepresentation()
      if volRenWidget is None:
        logging.error('Failed to access volume rendering module')
        return
      # Make sure the proper volume property node is set
      volumePropertyNode = self.volumeRenderingDisplayNode.GetVolumePropertyNode()
      if volumePropertyNode is None:
        logging.error('Failed to access volume properties')
        return
      volumePropertyNodeWidget = slicer.util.findChild(volRenWidget, 'VolumePropertyNodeWidget')
      volumePropertyNodeWidget.setMRMLVolumePropertyNode(volumePropertyNode)
      # Adjust the transfer function
      volumePropertyNodeWidget.moveAllPoints(self.VolumeRenderingShift, 0, False)


  def onToggleVolumeRenderingVisibilityButton(self):
      """
      Toggle volume rendering visibility and handle vesselmask visibility.
      """
      if not self.logic.maskedVolume: 
        self.logic.maskedVolume = slicer.mrmlScene.GetFirstNodeByName(self.logic.inputVolume.GetName() + f' masked volume')
        if not self.logic.maskedVolume: 
            slicer.util.warningDisplay("No masked volume found.\n")
        return

      segmentation = self.logic.outputSegmentation.GetSegmentation()
      _vesselmaskID = segmentation.GetSegmentIdBySegmentName("vesselmask")
 
      if not self.volumeRenderingDisplayNode:  
          self.updateVolumeRendering()
          if _vesselmaskID:
              self.logic.outputSegmentation.GetDisplayNode().SetSegmentVisibility(_vesselmaskID,False)
      else: 
          if not self.volumeRenderingDisplayNode.GetVisibility():   
              self.volumeRenderingDisplayNode.SetVisibility(True)
              if _vesselmaskID:
                self.logic.outputSegmentation.GetDisplayNode().SetSegmentVisibility(_vesselmaskID,False)
          else: 
              self.volumeRenderingDisplayNode.SetVisibility(False)
              if _vesselmaskID:
                self.logic.outputSegmentation.GetDisplayNode().SetSegmentVisibility(_vesselmaskID,True)

    
  def onStartButton(self):
      """
      Run processing when user clicks "Start" button.
      """
      if not self.logic.inputVolume: 
        slicer.util.warningDisplay("Please load and select an input volume!\n")
        return
      qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
      try:
          if self.ui.loadLastFiducialsCheckBox.checked:
            if not self.loadFiducialsDataDir(): 
                self.loadFiducialsTempDir() 
          self.setInstructions("Initializing segmentation...")
          self.isSufficientNumberOfPointsPlaced = False
          self.ui.updateIntensityButton.enabled = True          
          self.logic.startSegmentation()
          self.logic.updateSegmentation()
          self.updateGUIFromParameterNode()
          self.ui.toggleSegmentationVisibilityButton.enabled = False
          self.ui.toggleVolumeRenderingVisibilityButton.enabled = False
          self.ui.VolumeRenderingShiftSliderWidget.enabled = False
          # if AI checked and no airway segmentation run processing immediately from the start button          
          if self.useAI and not self.createDetailedAirways:
              self.runProcessing()
          qt.QApplication.restoreOverrideCursor()
      except Exception as e:
          qt.QApplication.restoreOverrideCursor()
          slicer.util.errorDisplay("Failed to start segmentation: "+str(e))
          import traceback
          traceback.print_exc()

  def runProcessing(self):
      """
      Run processing 
      """
      qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
      self.ui.updateIntensityButton.enabled = False

      try:
          self.logic.detailedAirways = self.createDetailedAirways
          self.logic.createVessels = self.createVessels
          self.logic.useAI = self.useAI
          self.logic.fastOption = self.fastOption
          if self.useAI:
            self.logic.engineAI = self.ui.engineAIComboBox.currentText
          # always save a copy of the current markups in Slicer temp dir for later use
          self.saveFiducialsTempDir()
          if self.saveFiducials: 
            self.saveFiducialsDataDir()
          self.setInstructions('Finalizing the segmentation, please wait...')
          self.logic.shrinkMasks = self.shrinkMasks
          self.logic.upgradeAI = self.upgradeAI
          self.logic.detailedMasks = self.detailedMasks
          self.logic.applySegmentation()
          segmentationNode = self.logic.outputSegmentation
          segmentationNode.CreateDefaultDisplayNodes()
          segmentationDisplayNode = segmentationNode.GetDisplayNode()
          segmentationDisplayNode.Visibility2DOn()
          segmentationDisplayNode.Visibility3DOn()
          self.volumeRenderingDisplayNode = None
          self.updateGUIFromParameterNode()
          self.ui.toggleSegmentationVisibilityButton.enabled = True
          self.ui.toggleVolumeRenderingVisibilityButton.enabled = True
          self.ui.VolumeRenderingShiftSliderWidget.enabled = True
          qt.QApplication.restoreOverrideCursor()
      except Exception as e:
          qt.QApplication.restoreOverrideCursor()
          slicer.util.errorDisplay("Failed to compute results: "+str(e))
          import traceback
          traceback.print_exc()
      self.setInstructions('')
      self.ui.applyButton.enabled = False

  def onApplyButton(self):
      """
      Run processing when user clicks "Apply" button.
      """
      self.runProcessing()

  def onCancelButton(self):
      """
      Stop segmentation without applying it.
      """
      try:
          self.logic.inputVolume = self.ui.inputVolumeSelector.currentNode()
          self.isSufficientNumberOfPointsPlaced = False
          self.logic.cancelSegmentation()
          self.ui.toggleSegmentationVisibilityButton.enabled = False
          self.ui.toggleVolumeRenderingVisibilityButton.enabled = False
          self.ui.startButton.enabled = True
          self.logic.segmentationStarted = False
          self.logic.segmentationFinished = False
          self.logic.rightLungFiducials = self.logic.leftLungFiducials = self.logic.tracheaFiducials = None
          self.updateGUIFromParameterNode()
          slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
      except Exception as e:
          slicer.util.errorDisplay("Failed to compute results: "+str(e))
          import traceback
          traceback.print_exc()

  def onUpdateIntensityButton(self):
      self.updateParameterNodeFromGUI()
      self.logic.updateSegmentation()

  def _saveFiducials(self, directory):
    try:
        markupsNode = slicer.mrmlScene.GetFirstNodeByName('R')
        temporaryStorageNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialStorageNode")
        temporaryStorageNode.SetFileName(directory+"R.fcsv")
        temporaryStorageNode.WriteData(markupsNode)
        slicer.mrmlScene.RemoveNode(temporaryStorageNode)  
        markupsNode = slicer.mrmlScene.GetFirstNodeByName('L')
        temporaryStorageNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialStorageNode")
        temporaryStorageNode.SetFileName(directory+"L.fcsv")
        temporaryStorageNode.WriteData(markupsNode)
        slicer.mrmlScene.RemoveNode(temporaryStorageNode)  
        markupsNode = slicer.mrmlScene.GetFirstNodeByName('T')
        temporaryStorageNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialStorageNode")
        temporaryStorageNode.SetFileName(directory+"T.fcsv")
        temporaryStorageNode.WriteData(markupsNode)
        slicer.mrmlScene.RemoveNode(temporaryStorageNode)  
    except Exception as e:
        slicer.util.errorDisplay("Failed to save markups: "+str(e))
        import traceback
        traceback.print_exc()
      
  def saveFiducialsTempDir(self):
    logging.info("Saving markups in temp directory ...")
    import os
    directory = slicer.app.temporaryPath + "/LungCTSegmenter/"
    if not os.path.exists(directory):
        os.makedirs(directory)
    self._saveFiducials(directory)

  def saveFiducialsDataDir(self):
    logging.info("Saving markups in volume directory ...")
    if not self.logic.inputVolume:
        logging.info("Error. Cannot get input volume node reference, unable to write to its volume directory. ")
    else: 
        storageNode = self.logic.inputVolume.GetStorageNode()
        if storageNode:
            inputFilename = storageNode.GetFileName()
            if inputFilename:
                baseFolder, tail = os.path.split(inputFilename)
            else:
                baseFolder = slicer.app.defaultScenePath
        else:
            baseFolder = slicer.app.defaultScenePath
        directory = baseFolder + "/LungCTSegmenter/"
        if not os.path.exists(directory):
            os.makedirs(directory)
        self._saveFiducials(directory)

  def loadFiducials(self,directory):

    RLoadSuccess = LLoadSuccess = TLoadSuccess = False 
    temporaryStorageNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialStorageNode")
    file_path = directory +"/R.fcsv"
    if os.path.exists(file_path): 
        if not self.logic.rightLungFiducials:
            self.logic.rightLungFiducials = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "R")
            self.logic.rightLungFiducials.CreateDefaultDisplayNodes()
            self.logic.rightLungFiducials.GetDisplayNode().SetSelectedColor(self.logic.brighterColor(self.logic.rightLungColor))
            self.logic.rightLungFiducials.GetDisplayNode().SetPointLabelsVisibility(True)
            temporaryStorageNode.SetFileName(file_path)
            temporaryStorageNode.ReadData(self.logic.rightLungFiducials)
            RLoadSuccess = True
    file_path = directory +"/L.fcsv"
    if os.path.exists(file_path): 
        if not self.logic.leftLungFiducials:
            self.logic.leftLungFiducials = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "L")
            self.logic.leftLungFiducials.CreateDefaultDisplayNodes()
            self.logic.leftLungFiducials.GetDisplayNode().SetSelectedColor(self.logic.brighterColor(self.logic.leftLungColor))
            self.logic.leftLungFiducials.GetDisplayNode().SetPointLabelsVisibility(True)
            temporaryStorageNode.SetFileName(file_path)
            temporaryStorageNode.ReadData(self.logic.leftLungFiducials)
            LLoadSuccess = True
    file_path = directory +"/T.fcsv"
    if os.path.exists(file_path): 
        if not self.logic.tracheaFiducials:
            self.logic.tracheaFiducials = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "T")
            self.logic.tracheaFiducials.CreateDefaultDisplayNodes()
            self.logic.tracheaFiducials.GetDisplayNode().SetSelectedColor(self.logic.brighterColor(self.logic.unknownColor))
            self.logic.tracheaFiducials.GetDisplayNode().SetPointLabelsVisibility(True)
            temporaryStorageNode.SetFileName(file_path)
            temporaryStorageNode.ReadData(self.logic.tracheaFiducials)
            TLoadSuccess = True
    slicer.mrmlScene.RemoveNode(temporaryStorageNode)
    
    if RLoadSuccess and LLoadSuccess and TLoadSuccess:
        return True
    else:
        return False 

  def loadFiducialsTempDir(self):
    import os.path

    fiducialsLoadSuccess = False
         
    # if not local markups available load last global  
    # logging.info("Loading last markups from temp directory ...")
    directory = slicer.app.temporaryPath + "/LungCTSegmenter/"
    if os.path.exists(directory): 
        fiducialsLoadSuccess = self.loadFiducials(directory)
        print("Loading last markups from temp directory ok.")

    if fiducialsLoadSuccess: 
        # start segmentation process and allow user to move or add additional markups
        self.onStartButton()
    return fiducialsLoadSuccess

  def loadFiducialsDataDir(self):
    import os.path

    fiducialsLoadSuccess = False
    # prefer local markups if available 
    # logging.info("Trying to load markups from volume directory ...")
    
    if not self.logic.inputVolume:
        logging.info("No input volume.")
    else: 
        storageNode = self.logic.inputVolume.GetStorageNode()
        if storageNode: 
            inputFilename = storageNode.GetFileName()
            head, tail = os.path.split(inputFilename)
            directory = head + "/LungCTSegmenter/"
            if not os.path.exists(directory):
                logging.info("No markup directory in data path.")
            else: 
                fiducialsLoadSuccess = self.loadFiducials(directory)
                logging.info("Succesfully loaded markups from volume directory.")
        else:
            logging.info("No storage node, probably node loaded from server.")
            
    if fiducialsLoadSuccess: 
        # start segmentation process and allow user to move or add additional markups
        self.onStartButton()
    return fiducialsLoadSuccess

#
# LungCTSegmenterLogic
#

class LungCTSegmenterLogic(ScriptedLoadableModuleLogic):
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
        self.rightLungSegmentId = None
        self.leftLungSegmentId = None
        self.tracheaSegmentId = None
        
        self.rightLungColor = (0.5, 0.68, 0.5)
        self.leftLungColor = (0.95, 0.84, 0.57)

        self.rightUpperLobeColor = (177./255., 122./255., 101./255. )
        self.rightMiddleLobeColor = (111./255., 184./255., 210./255.)
        self.rightLowerLobeColor = (216./255., 101./255., 79./255.)
        self.leftUpperLobeColor = (128./255., 174./255., 128./255.)
        self.leftLowerLobeColor = (241./255., 214./255., 145./255.)

        self.ribColor = (0.95, 0.84, 0.57)
        self.vesselMaskColor = (0.85, 0.40, 0.31)
        self.pulmonaryArteryColor = (0., 0.59, 0.81)
        self.pulmonaryVeinColor = (0.85, 0.40, 0.31)
        self.tracheaColor = (0.71, 0.89, 1.0)
        self.vesselmaskColor = (216./255., 160./255., 160./255.)
        self.PAColor = (0., 151./255., 206./255.)
        self.PVColor = (216./255., 101./255., 79./255.)
        self.tumorColor = (253./255., 135./255., 192./255.)
        self.thoracicCavityColor = (177./255., 122./255., 101./255.)
        self.unknownColor = (0.39, 0.39, 0.5)
        
        self.segmentEditorWidget = None
        self.segmentationStarted = False
        self.segmentationFinished = False
        self.detailedAirways = False
        self.createVessels = False
        self.useAI = False
        self.fastOption = False
        self.engineAI = "None"
        self.shrinkMasks = False
        self.upgradeAI = False
        self.detailedMasks = False
        self.maskedVolume = None
        
    def __del__(self):
        self.removeTemporaryObjects()

    def setDefaultParameters(self, parameterNode):
        """
        Initialize parameter node with default settings.
        """
        if not parameterNode.GetParameter("LungThresholdMin"):
          parameterNode.SetParameter("LungThresholdMin", "-1500")
        if not parameterNode.GetParameter("LungThresholdMax"):
          parameterNode.SetParameter("LungThresholdMax", "-400")
        if not parameterNode.GetParameter("AirwayThresholdMin"):
          parameterNode.SetParameter("AirwayThresholdMin", "-1500")
        if not parameterNode.GetParameter("AirwayThresholdMax"):
          parameterNode.SetParameter("AirwayThresholdMax", "-850")
        if not parameterNode.GetParameter("VesselThresholdMin"):
          parameterNode.SetParameter("VesselThresholdMin", "0")
        if not parameterNode.GetParameter("VesselThresholdMax"):
          parameterNode.SetParameter("VesselThresholdMax", "3000")
        if not parameterNode.GetParameter("airwaySegmentationDetailLevel"):
          parameterNode.SetParameter("airwaySegmentationDetailLevel", "3")
        if not parameterNode.GetParameter("engineAI"):
          parameterNode.SetParameter("engineAI", "lungmask")
    @property
    def lungThresholdMin(self):
        thresholdStr = self.getParameterNode().GetParameter("LungThresholdMin")
        return float(thresholdStr) if thresholdStr else -1024

    @lungThresholdMin.setter
    def lungThresholdMin(self, value):
        self.getParameterNode().SetParameter("LungThresholdMin", str(value))

    @property
    def lungThresholdMax(self):
        thresholdStr = self.getParameterNode().GetParameter("LungThresholdMax")
        return float(thresholdStr) if thresholdStr else -400

    @lungThresholdMax.setter
    def lungThresholdMax(self, value):
        self.getParameterNode().SetParameter("LungThresholdMax", str(value))

    @property
    def airwayThresholdMin(self):
        thresholdStr = self.getParameterNode().GetParameter("AirwayThresholdMin")
        return float(thresholdStr) if thresholdStr else -1500

    @airwayThresholdMin.setter
    def airwayThresholdMin(self, value):
        self.getParameterNode().SetParameter("AirwayThresholdMin", str(value))

    @property
    def airwayThresholdMax(self):
        thresholdStr = self.getParameterNode().GetParameter("AirwayThresholdMax")
        return float(thresholdStr) if thresholdStr else -850

    @airwayThresholdMax.setter
    def airwayThresholdMax(self, value):
        self.getParameterNode().SetParameter("AirwayThresholdMax", str(value))

    @property
    def vesselThresholdMin(self):
        thresholdStr = self.getParameterNode().GetParameter("VesselThresholdMin")
        return float(thresholdStr) if thresholdStr else 0

    @vesselThresholdMin.setter
    def vesselThresholdMin(self, value):
        self.getParameterNode().SetParameter("VesselThresholdMin", str(value))

    @property
    def vesselThresholdMax(self):
        thresholdStr = self.getParameterNode().GetParameter("VesselThresholdMax")
        return float(thresholdStr) if thresholdStr else 3000

    @vesselThresholdMax.setter
    def vesselThresholdMax(self, value):
        self.getParameterNode().SetParameter("VesselThresholdMax", str(value))

    @property
    def inputVolume(self):
        return self.getParameterNode().GetNodeReference("InputVolume")

    @inputVolume.setter
    def inputVolume(self, node):
        self.getParameterNode().SetNodeReferenceID("InputVolume", node.GetID() if node else None)

    @property
    def outputSegmentation(self):
        return self.getParameterNode().GetNodeReference("OutputSegmentation")

    @outputSegmentation.setter
    def outputSegmentation(self, node):
        self.getParameterNode().SetNodeReferenceID("OutputSegmentation", node.GetID() if node else None)

    @property
    def resampledVolume(self):
        return self.getParameterNode().GetNodeReference("ResampledVolume")

    @resampledVolume.setter
    def resampledVolume(self, node):
        self.getParameterNode().SetNodeReferenceID("ResampledVolume", node.GetID() if node else None)

    @property
    def rightLungFiducials(self):
        return self.getParameterNode().GetNodeReference("RightLungFiducials")

    @rightLungFiducials.setter
    def rightLungFiducials(self, node):
        self.getParameterNode().SetNodeReferenceID("RightLungFiducials", node.GetID() if node else None)

    @property
    def leftLungFiducials(self):
        return self.getParameterNode().GetNodeReference("LeftLungFiducials")

    @leftLungFiducials.setter
    def leftLungFiducials(self, node):
        self.getParameterNode().SetNodeReferenceID("LeftLungFiducials", node.GetID() if node else None)

    @property
    def airwaySegmentationDetailLevel(self):
        return self.getParameterNode().GetParameter("AirwaySegmentationDetailLevel")

    @airwaySegmentationDetailLevel.setter
    def airwaySegmentationDetailLevel(self, _str):
        self.getParameterNode().SetParameter("AirwaySegmentationDetailLevel", _str)

    @property
    def tracheaFiducials(self):
        return self.getParameterNode().GetNodeReference("TracheaFiducials")

    @tracheaFiducials.setter
    def tracheaFiducials(self, node):
        self.getParameterNode().SetNodeReferenceID("TracheaFiducials", node.GetID() if node else None)

    @property
    def engineAI(self):
        return self.getParameterNode().GetParameter("EngineAI")

    @engineAI.setter
    def engineAI(self, _name):
        self.getParameterNode().SetParameter("EngineAI", _name)

    def brighterColor(self, rgb):
        import numpy as np
        scaleFactor = 1.5
        rgbBrighter = np.array(rgb) * scaleFactor
        return np.clip(rgbBrighter, 0.0, 1.0)

    def startSegmentation(self):
        if not self.inputVolume:
          # prevent start
          raise ValueError("No input volume. ")
          return
        if self.segmentationStarted:
          # Already started
          return
        self.segmentationStarted = True
        self.segmentationFinished = False
        
        import time
        startTime = time.time()

        # Clear previous segmentation
        if self.outputSegmentation:
            self.outputSegmentation.GetSegmentation().RemoveAllSegments()

        if not self.rightLungFiducials:
            self.rightLungFiducials = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "R")
            self.rightLungFiducials.CreateDefaultDisplayNodes()
            self.rightLungFiducials.GetDisplayNode().SetSelectedColor(self.brighterColor(self.rightLungColor))
            self.rightLungFiducials.GetDisplayNode().SetPointLabelsVisibility(True)
        if not self.leftLungFiducials:
            self.leftLungFiducials = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "L")
            self.leftLungFiducials.CreateDefaultDisplayNodes()
            self.leftLungFiducials.GetDisplayNode().SetSelectedColor(self.brighterColor(self.leftLungColor))
            self.leftLungFiducials.GetDisplayNode().SetPointLabelsVisibility(True)
        if not self.tracheaFiducials:
            self.tracheaFiducials = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "T")
            self.tracheaFiducials.CreateDefaultDisplayNodes()
            self.tracheaFiducials.GetDisplayNode().SetSelectedColor(self.brighterColor(self.unknownColor))
            self.tracheaFiducials.GetDisplayNode().SetPointLabelsVisibility(True)

        if not self.resampledVolume:
            self.resampledVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Resampled Volume")

        # Get window / level of inputVolume 
        displayNode = self.inputVolume.GetDisplayNode()
        displayNode.AutoWindowLevelOff()
        displayNode.SetWindowLevel(1400, -500)

        # Create resampled volume with fixed 2.0mm spacing (for faster, standardized workflow)

        self.showStatusMessage('Resampling volume, please wait...')
        parameters = {"outputPixelSpacing": "2.0,2.0,2.0", "InputVolume": self.inputVolume, "interpolationType": "linear", "OutputVolume": self.resampledVolume}
        cliParameterNode = slicer.cli.runSync(slicer.modules.resamplescalarvolume, None, parameters)
        slicer.mrmlScene.RemoveNode(cliParameterNode)
        
        # Set window / level of inputVolume in resampledVolume 
        displayNode = self.resampledVolume.GetDisplayNode()
        displayNode.AutoWindowLevelOff()
        displayNode.SetWindowLevel(1400, -500)

        if not self.outputSegmentation:
            self.outputSegmentation = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "Lung segmentation")
            self.outputSegmentation.CreateDefaultDisplayNodes()
        # We show the current segmentation using markups, so let's hide the display node (seeds)
        self.rightLungSegmentId = None
        self.leftLungSegmentId = None
        self.tracheaSegmentId = None
        self.outputSegmentation.GetDisplayNode().SetVisibility(False)
        self.outputSegmentation.SetReferenceImageGeometryParameterFromVolumeNode(self.resampledVolume)

        # Create temporary segment editor to get access to effects
        self.segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
        self.segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
        self.segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        self.segmentEditorWidget.setMRMLSegmentEditorNode(self.segmentEditorNode)
        self.segmentEditorWidget.setSegmentationNode(self.outputSegmentation)
        self.segmentEditorWidget.setSourceVolumeNode(self.resampledVolume)

        self.segmentEditorWidget.mrmlSegmentEditorNode().SetMasterVolumeIntensityMask(True)
        intensityRange = [self.lungThresholdMin, self.lungThresholdMax]
        self.segmentEditorWidget.mrmlSegmentEditorNode().SetSourceVolumeIntensityMaskRange(intensityRange)

        stopTime = time.time()
        logging.info('StartSegmentation completed in {0:.2f} seconds'.format(stopTime-startTime))
        
    def updateSeedSegmentFromMarkups(self, segmentName, markupsNode, color, radius, segmentId):
        if segmentId:
            self.outputSegmentation.GetSegmentation().RemoveSegment(segmentId)
        append = vtk.vtkAppendPolyData()
        numFids = markupsNode.GetNumberOfFiducials()
        for i in range(numFids):
            ras = [0,0,0]
            markupsNode.GetNthFiducialPosition(i,ras)
            sphere = vtk.vtkSphereSource()
            sphere.SetCenter(ras)
            sphere.SetRadius(radius)
            sphere.Update()
            append.AddInputData(sphere.GetOutput())
        append.Update()
        return self.outputSegmentation.AddSegmentFromClosedSurfaceRepresentation(append.GetOutput(), segmentName, color)

    def updateSegmentation(self):
      """
      Finalize the previewed segmentation.
      """
      
      if self.useAI: 
        return

      if (not self.rightLungFiducials or self.rightLungFiducials.GetNumberOfControlPoints() < 6
          or not self.leftLungFiducials or self.leftLungFiducials.GetNumberOfControlPoints() < 6
          or not self.tracheaFiducials or self.tracheaFiducials.GetNumberOfControlPoints() < 1):
          # not yet ready for region growing
          self.showStatusMessage('Not enough markups ...')
          return

      self.showStatusMessage('Update segmentation...')
      self.rightLungSegmentId = self.updateSeedSegmentFromMarkups("right lung", self.rightLungFiducials, self.rightLungColor, 10.0, self.rightLungSegmentId)
      self.leftLungSegmentId = self.updateSeedSegmentFromMarkups("left lung", self.leftLungFiducials, self.leftLungColor, 10.0, self.leftLungSegmentId)
      self.tracheaSegmentId = self.updateSeedSegmentFromMarkups("other", self.tracheaFiducials, self.unknownColor, 2.0, self.tracheaSegmentId)

      # Activate region growing segmentation
      self.showStatusMessage('Region growing...')

      # Set intensity mask and thresholds again to reflect their possible changes and update button
      self.segmentEditorWidget.mrmlSegmentEditorNode().SetMasterVolumeIntensityMask(True)
      intensityRange = [self.lungThresholdMin, self.lungThresholdMax]
      self.segmentEditorWidget.mrmlSegmentEditorNode().SetSourceVolumeIntensityMaskRange(intensityRange)
      # set effect
      self.segmentEditorWidget.setActiveEffectByName("Grow from seeds")
      effect = self.segmentEditorWidget.activeEffect()
      # extent farther from control points than usual to capture lung edges
      effect.self().extentGrowthRatio = 0.5
      effect.self().onPreview()
      #effect.self().setPreviewOpacity(0.5)
      effect.self().setPreviewShow3D(True)
      # center 3D view
      layoutManager = slicer.app.layoutManager()
      threeDWidget = layoutManager.threeDWidget(0)
      threeDView = threeDWidget.threeDView()
      threeDView.resetFocalPoint()

    def removeTemporaryObjects(self):
        if self.resampledVolume:
            slicer.mrmlScene.RemoveNode(self.resampledVolume)
        if self.segmentEditorWidget:
            self.segmentEditorNode = self.segmentEditorWidget.mrmlSegmentEditorNode()
            # Cancel "Grow from seeds" (deletes preview segmentation)
            self.segmentEditorWidget.setActiveEffectByName("Grow from seeds")
            effect = self.segmentEditorWidget.activeEffect()
            if effect:
                effect.self().reset()
            # Deactivates all effects
            self.segmentEditorWidget.setActiveEffect(None)
            self.segmentEditorWidget = None
            slicer.mrmlScene.RemoveNode(self.segmentEditorNode)

    def cancelSegmentation(self):
        if self.outputSegmentation:
            self.outputSegmentation.GetSegmentation().RemoveAllSegments()
            self.rightLungSegmentId = None
            self.leftLungSegmentId = None
            self.tracheaSegmentId = None
        self.removeTemporaryObjects()
        slicer.mrmlScene.RemoveNode(self.rightLungFiducials)
        slicer.mrmlScene.RemoveNode(self.leftLungFiducials)
        slicer.mrmlScene.RemoveNode(self.tracheaFiducials)
        slicer.mrmlScene.RemoveNode(slicer.mrmlScene.GetFirstNodeByName("Lung segmentation"))
        slicer.mrmlScene.RemoveNode(slicer.mrmlScene.GetFirstNodeByName("TotalSegmentator"))
        if self.maskedVolume: 
            slicer.mrmlScene.RemoveNode(self.maskedVolume)
        
        self.removeTemporaryObjects()

        self.segmentationStarted = False

    def showStatusMessage(self, msg, timeoutMsec=500):
        slicer.util.showStatusMessage(msg, timeoutMsec)
        slicer.app.processEvents()

    def trimSegmentWithCube(self, id,r,a,s,offs_r,offs_a,offs_s) :
          
        self.segmentEditorNode.SetSelectedSegmentID(id)
        self.segmentEditorWidget.setActiveEffectByName("Surface cut")

        effect = self.segmentEditorWidget.activeEffect()

        effect.self().fiducialPlacementToggle.placeButton().click()
        
            
        # trim with cube

        points =[[r-offs_r, a+offs_a, s+offs_s], [r+offs_r, a+offs_a, s+offs_s],
                 [r+offs_r, a+offs_a, s-offs_s], [r-offs_r, a+offs_a, s-offs_s],
                 [r-offs_r, a-offs_a, s+offs_s], [r+offs_r, a-offs_a, s+offs_s],
                 [r+offs_r, a-offs_a, s-offs_s], [r-offs_r, a-offs_a, s-offs_s],
                ]

        for p in points:
            effect.self().segmentMarkupNode.AddFiducialFromArray(p)
        
        effect.setParameter("Operation","ERASE_INSIDE")
        effect.setParameter("SmoothModel","0")

        effect.self().onApply()
        

    def createSubSegment(self,segmentId,name): 
        segmentName = self.outputSegmentation.GetSegmentation().GetSegment(segmentId).GetName()
        newSeg = slicer.vtkSegment()
        newSeg.SetName(segmentName + " " + name)
        if segmentId == self.rightLungSegmentId: 
            newSeg.SetColor(self.rightLungColor)
        else: 
            newSeg.SetColor(self.leftLungColor)
        self.outputSegmentation.GetSegmentation().AddSegment(newSeg,segmentName + " " + name)                
        newSeg.DeepCopy(self.outputSegmentation.GetSegmentation().GetSegment(segmentId))
        newSeg.SetName(segmentName + " " + name)
        self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(newSeg.GetName(),False)

        return newSeg


    def createDetailedMasks(self): 
        segmentationNode = self.outputSegmentation

        # Compute centroids
        self.showStatusMessage('Computing centroids ...')
        import SegmentStatistics
        segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
        segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.centroid_ras.enabled", str(True))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_origin_ras.enabled",str(True))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_diameter_mm.enabled",str(True))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_x.enabled",str(True))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_y.enabled",str(True))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_z.enabled",str(True))
        segStatLogic.computeStatistics()
        stats = segStatLogic.getStatistics()

        # Place a markup point in each centroid
        markupsNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsNode.CreateDefaultDisplayNodes()
        for segmentId in stats['SegmentIDs']:
            if segmentId == self.rightLungSegmentId or segmentId == self.leftLungSegmentId:

                # get centroid
                centroid_ras = stats[segmentId,"LabelmapSegmentStatisticsPlugin.centroid_ras"]
                # get bounding box
                import numpy as np
                obb_origin_ras = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_origin_ras"])
                obb_diameter_mm = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_diameter_mm"])
                obb_direction_ras_x = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_x"])
                obb_direction_ras_y = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_y"])
                obb_direction_ras_z = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_z"])
                obb_center_ras = obb_origin_ras+0.5*(obb_diameter_mm[0] * obb_direction_ras_x + obb_diameter_mm[1] * obb_direction_ras_y + obb_diameter_mm[2] * obb_direction_ras_z)
                axialLungDiameter = obb_diameter_mm[0]
                sagittalLungDiameter = obb_diameter_mm[1]
                coronalLungDiameter = obb_diameter_mm[2]
                coronalApex = centroid_ras[2] + (coronalLungDiameter/2.)
                                
                segmentName = segmentationNode.GetSegmentation().GetSegment(segmentId).GetName()
                markupsNode.AddFiducialFromArray(centroid_ras, segmentName)
                
                self.showStatusMessage('Creating special masks ...')
                anterior = self.createSubSegment(segmentId, "anterior")
                posterior = self.createSubSegment(segmentId, "posterior")
                upper = self.createSubSegment(segmentId, "upper")
                middle = self.createSubSegment(segmentId, "middle")
                lower = self.createSubSegment(segmentId, "lower")
                
                ####### anterior
                
                r = centroid_ras[0]
                a = centroid_ras[1] - (sagittalLungDiameter/2.)
                s = centroid_ras[2]
                
                
                crop_r = axialLungDiameter  
                crop_a = (sagittalLungDiameter/2.)
                crop_s = coronalLungDiameter
                
                self.showStatusMessage(' Cropping anterior mask ...')
                self.trimSegmentWithCube(anterior.GetName(),r,a,s,crop_r,crop_a,crop_s)

                ####### posterior
                
                r = centroid_ras[0]
                a = centroid_ras[1] + (sagittalLungDiameter/2.)
                s = centroid_ras[2]
                
                crop_r = axialLungDiameter
                crop_a = (sagittalLungDiameter/2.)
                crop_s = coronalLungDiameter

                self.showStatusMessage(' Cropping posterior mask ...')
                self.trimSegmentWithCube(posterior.GetName(),r,a,s,crop_r,crop_a,crop_s)

                ####### upper
                
                r = centroid_ras[0]
                a = centroid_ras[1] 
                s = coronalApex - coronalLungDiameter
                
                crop_r = axialLungDiameter
                crop_a = sagittalLungDiameter
                crop_s = (coronalLungDiameter/3.) * 2.

                self.showStatusMessage(' Cropping upper mask ...')
                self.trimSegmentWithCube(upper.GetName(),r,a,s,crop_r,crop_a,crop_s)
           
                ####### middle
                
                ####### crop upper part
                r = centroid_ras[0]
                a = centroid_ras[1] 
                s = coronalApex

                
                crop_r = axialLungDiameter 
                crop_a = sagittalLungDiameter
                crop_s = (coronalLungDiameter/3.)

                self.showStatusMessage(' Cropping middle mask ...')
                self.trimSegmentWithCube(middle.GetName(),r,a,s,crop_r,crop_a,crop_s)

                ####### crop lower part
                r = centroid_ras[0]
                a = centroid_ras[1] 
                s = coronalApex - coronalLungDiameter 

                crop_r = axialLungDiameter  
                crop_a = sagittalLungDiameter
                crop_s = (coronalLungDiameter/3.)

                self.trimSegmentWithCube(middle.GetName(),r,a,s,crop_r,crop_a,crop_s)

                ####### lower
                
                r = centroid_ras[0]
                a = centroid_ras[1] 
                s = coronalApex

                
                crop_r = axialLungDiameter  
                crop_a = sagittalLungDiameter
                crop_s = (coronalLungDiameter/3.)*2.

                self.showStatusMessage(' Cropping lower mask ...')
                self.trimSegmentWithCube(lower.GetName(),r,a,s,crop_r,crop_a,crop_s)


    def postprocessSegment(self, outputSegmentation, _nth, segmentName):
        outputSegmentation.GetSegmentation().GetNthSegment(_nth).SetName(segmentName)
        _segID = outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(segmentName)

        if self.useAI:
            self.segmentEditorWidget.setSegmentationNode(outputSegmentation)
            self.segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone) 
            self.segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)
            self.showStatusMessage(f'Smoothing {segmentName}')
            self.segmentEditorNode.SetSelectedSegmentID(_segID)
            self.segmentEditorWidget.setActiveEffectByName("Smoothing")
            effect = self.segmentEditorWidget.activeEffect()
            effect.setParameter("SmoothingMethod","GAUSSIAN")
            effect.setParameter("GaussianStandardDeviationMm","2")
            effect.self().onApply()

        displayNode = outputSegmentation.GetDisplayNode()
        # Set overall opacity of the segmentation
        displayNode.SetOpacity3D(1.0)  
        # Set opacity of a single segment
        displayNode.SetSegmentOpacity3D(_segID, 0.3)  
        self.setAnatomicalTag(self.outputSegmentation, segmentName, _segID)
        


    def addSegmentFromNumpyArray(self, outputSegmentation, input_np, segmentName, labelValue, inputVolume, color):
        emptySegment = slicer.vtkSegment()
        emptySegment.SetName(segmentName)
        emptySegment.SetColor(color)
        outputSegmentation.GetSegmentation().AddSegment(emptySegment)

        import numpy as np
        segment_np = np.zeros(input_np.shape)
        segment_np[ input_np==labelValue ] = 1

        segmentId = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
        slicer.util.updateSegmentBinaryLabelmapFromArray(segment_np, outputSegmentation, segmentId, inputVolume)


    def normalizeImageHU(self, img, air, fat):
        air_HU = -1000
        fat_HU = -100
        
        delta_air_fat_HU = abs(air_HU - fat_HU)
        delta_air = abs(air - air_HU)
        delta_fat_air_rgb = abs(fat - air)
        ratio = delta_air_fat_HU / delta_fat_air_rgb
        
        img = img - air
        img = img * ratio
        img = img + air_HU
        return img

    def get_script_path(self):
        return os.path.dirname(os.path.realpath(sys.argv[0]))

    def setAnatomicalTag(self, _outputsegmentation, _name, _segID):
        segment = _outputsegmentation.GetSegmentation().GetSegment(_segID)
        if _name == "right lung": 
            segment.SetTag(segment.GetTerminologyEntryTagName(),
                "Segmentation category and type - 3D Slicer General Anatomy list"
                "~SCT^123037004^Anatomical Structure"
                "~SCT^39607008^Lung"
                "~SCT^24028007^Right"
                "~Anatomic codes - DICOM master list"
                "~^^"
                "~^^")
        elif _name == "left lung":
            segment.SetTag(segment.GetTerminologyEntryTagName(),
                "Segmentation category and type - 3D Slicer General Anatomy list"
                "~SCT^123037004^Anatomical Structure"
                "~SCT^39607008^Lung"
                "~SCT^7771000^Left"
                "~Anatomic codes - DICOM master list"
                "~^^"
                "~^^")
        elif _name == "left upper lobe":
            segment.SetTag(segment.GetTerminologyEntryTagName(),
                "Segmentation category and type - 3D Slicer General Anatomy list"
                "~SCT^123037004^Anatomical Structure"
                "~SCT^45653009^Upper lobe of Lung"
                "~SCT^7771000^Left"
                "~Anatomic codes - DICOM master list"
                "~^^"
                "~^^")
        elif _name == "left lower lobe":
            segment.SetTag(segment.GetTerminologyEntryTagName(),
                "Segmentation category and type - 3D Slicer General Anatomy list"
                "~SCT^123037004^Anatomical Structure"
                "~SCT^90572001^Lower lobe of lung"
                "~SCT^7771000^Left"
                "~Anatomic codes - DICOM master list"
                "~^^"
                "~^^")
        elif _name == "right upper lobe":
            segment.SetTag(segment.GetTerminologyEntryTagName(),
                "Segmentation category and type - 3D Slicer General Anatomy list"
                "~SCT^123037004^Anatomical Structure"
                "~SCT^45653009^Upper lobe of lung"
                "~SCT^24028007^Right"
                "~Anatomic codes - DICOM master list"
                "~^^"
                "~^^")
        elif _name == "right middle lobe":
            segment.SetTag(segment.GetTerminologyEntryTagName(),
                "Segmentation category and type - 3D Slicer General Anatomy list"
                "~SCT^123037004^Anatomical Structure"
                "~SCT^72481006^Middle lobe of lung"
                "~SCT^24028007^Right"
                "~Anatomic codes - DICOM master list"
                "~^^"
                "~^^")
        elif _name == "right lower lobe":
            segment.SetTag(segment.GetTerminologyEntryTagName(),
                "Segmentation category and type - 3D Slicer General Anatomy list"
                "~SCT^123037004^Anatomical Structure"
                "~SCT^90572001^Lower lobe of lung"
                "~SCT^24028007^Right"
                "~Anatomic codes - DICOM master list"
                "~^^"
                "~^^")
        elif _name == "airways":
            segment.SetTag(segment.GetTerminologyEntryTagName(),
              "Segmentation category and type - 3D Slicer General Anatomy list"
              "~SCT^123037004^Anatomical Structure"
              "~SCT^44567001^Trachea"
              "~^^"
              "~Anatomic codes - DICOM master list"
              "~^^"
              "~^^")
        #else:
        #    print(_name + " not handled during SetTag.")
        
                       
    def importTotalSegmentatorSegment(self, _outputName, _inputName, _outputsegmentation, _inputsegmentation, _color):
        
        sourceSegmentId = None
        sourceSegmentId = _inputsegmentation.GetSegmentation().GetSegmentIdBySegmentName(_inputName)
        if sourceSegmentId:
            _outputsegmentation.GetSegmentation().CopySegmentFromSegmentation(_inputsegmentation.GetSegmentation(), sourceSegmentId)
            _segID = _outputsegmentation.GetSegmentation().GetSegmentIdBySegmentName(_inputName)
            _outputsegmentation.GetSegmentation().GetSegment(_segID).SetName(_outputName)
            _outputsegmentation.GetSegmentation().GetSegment(_segID).SetColor(_color)
            self.setAnatomicalTag(_outputsegmentation, _outputName, _segID)
            displayNode = _outputsegmentation.GetDisplayNode()
            # Set overall opacity of the segmentation
            displayNode.SetOpacity3D(1.0)  
            if _outputName.find("lobe") > -1 or _outputName.find("lung") > -1:
                # smooth segment
                self.segmentEditorWidget.setSegmentationNode(_outputsegmentation)
                self.segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone) 
                self.segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)
                self.showStatusMessage(f'Smoothing {_outputName}')
                self.segmentEditorNode.SetSelectedSegmentID(_segID)
                self.segmentEditorWidget.setActiveEffectByName("Smoothing")
                effect = self.segmentEditorWidget.activeEffect()
                effect.setParameter("SmoothingMethod","GAUSSIAN")
                effect.setParameter("GaussianStandardDeviationMm","2")
                effect.self().onApply()
                # make lobes semitransparent
                # Set opacity of a single segment
                displayNode.SetSegmentOpacity3D(_segID, 0.3)  

    def saveVolTemp(self, inputVolume):
        import time
        import tempfile

        # Temporary folder path
        tempVolDir = slicer.app.temporaryPath + "/LungCTSegmenter/"
        # Select the volume node you are trying to work with
        volNode = inputVolume
        image_id = volNode.GetName()
        # Absolute path of the temporary volume file
        in_file = tempfile.NamedTemporaryFile(suffix= '.nrrd', dir = tempVolDir).name
        # save the volume node
        start = time.time()
        slicer.util.saveNode(volNode, in_file)
        logging.info(f"Saved Input Node into {in_file} in {time.time() - start:3.1f}s")
        return tempVolDir, image_id, in_file

    def addSegment(self, _segmentation, _name, _color, _opacity = 1.0):
        newSeg = slicer.vtkSegment()
        newSeg.SetName(_name)
        newSeg.SetColor(_color)
        _segmentation.GetSegmentation().AddSegment(newSeg,_name)
        _segid = _segmentation.GetSegmentation().GetSegmentIdBySegmentName(_name)
        displayNode = _segmentation.GetDisplayNode()
        displayNode.SetSegmentOpacity3D(_segid, _opacity)  

        return _segid

    def slicerVersionToFloat(self):
        return float(str(slicer.app.majorVersion) + "." + str(slicer.app.minorVersion))

    def openFile(self, filename):
        if sys.platform == "win32":
            filename.replace('/', '\\')
            os.startfile(filename)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, filename])

    def addSegmentToSegment(self, segmentation, modifierSegmentID, selectedSegmentID):
        self.showStatusMessage('Adding ' + modifierSegmentID + ' to ' + selectedSegmentID + ' ...')
        self.segmentEditorWidget.setSegmentationNode(segmentation)
        self.segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone) 
        self.segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)
        self.segmentEditorNode.SetSelectedSegmentID(selectedSegmentID)
        self.segmentEditorWidget.setActiveEffectByName("Logical operators")
        effect = self.segmentEditorWidget.activeEffect()
        effect.setParameter("BypassMasking","1")
        effect.setParameter("ModifierSegmentID",modifierSegmentID)
        effect.setParameter("Operation","UNION")
        effect.self().onApply()


    def applySegmentation(self):
        if not self.segmentEditorWidget.activeEffect() and not self.useAI:
            # no region growing was done
            return

        import time
        startTime = time.time()

        if not self.useAI: 
            self.showStatusMessage('Finalize region growing...')
            # Ensure closed surface representation is not present (would slow down computations)
            self.outputSegmentation.RemoveClosedSurfaceRepresentation()

            self.segmentEditorNode = self.segmentEditorWidget.mrmlSegmentEditorNode()
            self.segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteAllSegments) 
            self.segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)

            effect = self.segmentEditorWidget.activeEffect()
            effect.self().onApply()

            # disable intensity masking, otherwise vessels do not fill
            self.segmentEditorNode.SetMasterVolumeIntensityMask(False)

            # Prevent confirmation popup for editing a hidden segment
            previousConfirmEditHiddenSegmentSetting = slicer.app.settings().value("Segmentations/ConfirmEditHiddenSegment")
            slicer.app.settings().setValue("Segmentations/ConfirmEditHiddenSegment", qt.QMessageBox.No)

            segmentIds = [self.rightLungSegmentId, self.leftLungSegmentId, self.tracheaSegmentId]
            
            # fill holes
            for i, segmentId in enumerate(segmentIds):
                self.showStatusMessage(f'Filling holes ({i+1}/{len(segmentIds)})...')
                self.segmentEditorNode.SetSelectedSegmentID(segmentId)
                self.segmentEditorWidget.setActiveEffectByName("Smoothing")
                effect = self.segmentEditorWidget.activeEffect()
                effect.setParameter("SmoothingMethod","MORPHOLOGICAL_CLOSING")
                effect.setParameter("KernelSizeMm","12")
                effect.self().onApply()

            # switch to full-resolution segmentation (this is quick, there is no need for progress message)
            self.outputSegmentation.SetReferenceImageGeometryParameterFromVolumeNode(self.inputVolume)
            referenceGeometryString = self.outputSegmentation.GetSegmentation().GetConversionParameter(slicer.vtkSegmentationConverter.GetReferenceImageGeometryParameterName())
            referenceGeometryImageData = slicer.vtkOrientedImageData()
            slicer.vtkSegmentationConverter.DeserializeImageGeometry(referenceGeometryString, referenceGeometryImageData, False)
            wasModified = self.outputSegmentation.StartModify()
            for i, segmentId in enumerate(segmentIds):
                currentSegment = self.outputSegmentation.GetSegmentation().GetSegment(segmentId)
                # Get master labelmap from segment
                currentLabelmap = currentSegment.GetRepresentation("Binary labelmap")
                # Resample
                if not slicer.vtkOrientedImageDataResample.ResampleOrientedImageToReferenceOrientedImage(
                  currentLabelmap, referenceGeometryImageData, currentLabelmap, False, True):
                  raise ValueError("Failed to resample segment " << currentSegment.GetName())
            self.segmentEditorWidget.setSourceVolumeNode(self.inputVolume)
            # Trigger display update
            self.outputSegmentation.Modified()
            self.outputSegmentation.EndModify(wasModified)

            # smoothing
            for i, segmentId in enumerate(segmentIds):
                self.showStatusMessage(f'Smoothing ({i+1}/{len(segmentIds)})...')
                self.segmentEditorNode.SetSelectedSegmentID(segmentId)
                self.segmentEditorWidget.setActiveEffectByName("Smoothing")
                effect = self.segmentEditorWidget.activeEffect()
                effect.setParameter("SmoothingMethod","GAUSSIAN")
                effect.setParameter("GaussianStandardDeviationMm","2")
                effect.self().onApply()
            
            if self.shrinkMasks: 
                # Final shrinking masks by 1 mm
                for i, segmentId in enumerate(segmentIds):
                    self.showStatusMessage(f'Final shrinking ({i+1}/{len(segmentIds)})...')
                    self.segmentEditorNode.SetSelectedSegmentID(segmentId)
                    self.segmentEditorWidget.setActiveEffectByName("Margin")
                    effect = self.segmentEditorWidget.activeEffect()
                    effect.setParameter("MarginSizeMm","-1")
                    effect.self().onApply()
            
            if self.detailedMasks: 
                self.createDetailedMasks()

            # Postprocess lungs and set tags
            self.postprocessSegment(self.outputSegmentation,0,"right lung")
            self.postprocessSegment(self.outputSegmentation,1,"left lung")
        _doAI = False
        if self.useAI:
            # Install PyTorch
            if not hasattr(slicer.modules, 'pytorchutils'):
                slicer.util.messageBox("AI segmentation requires the PyTorchUtils module in the PyTorch extension. Install Pytorch and restart Slicer.")
                return
            import PyTorchUtils
            torchLogic = PyTorchUtils.PyTorchUtilsLogic()
            if not torchLogic.torchInstalled():
                logging.info('Torchlogic module not found')
                torch = torchLogic.installTorch(askConfirmation=True)
                if torch is None:
                  raise ValueError('Torch needs to be installed to use this module.')
            else:
                import torch
            if not torch.cuda.is_available():
                logging.info('Pytorch CUDA is not available. AI will use CPU processing.')
                if not slicer.util.confirmYesNoDisplay("Warning: Pytorch CUDA is not found on your system. The AI processing will last 3-10 minutes. Are you sure you want to continue AI segmentation?"):
                    _doAI = False
                    logging.info('AI processing cancelled by user.')
                else:
                    _doAI = True
            else: 
                _doAI = True
                logging.info('Pytorch CUDA is available. AI will use GPU processing.')
        if _doAI:
            # use unsampled, original input volume and set geometry
            self.outputSegmentation.SetReferenceImageGeometryParameterFromVolumeNode(self.inputVolume)
            wasModified = self.outputSegmentation.StartModify()
            self.segmentEditorWidget.setSourceVolumeNode(self.inputVolume)
            # Trigger display update
            self.outputSegmentation.Modified()
            self.outputSegmentation.EndModify(wasModified)
            if self.engineAI.find("lungmask") == 0:
                # Import the required libraries
                self.showStatusMessage(' Importing lungmask AI ...')
                try:
                    import lungmask
                except ModuleNotFoundError:
                    slicer.util.pip_install("git+https://github.com/JoHof/lungmask")
                    import lungmask
                
                from lungmask import mask
                
                if self.upgradeAI:
                    slicer.util.pip_install("git+https://github.com/JoHof/lungmask --upgrade")
                    
                inputVolumeSitk = sitkUtils.PullVolumeFromSlicer(self.inputVolume)
                if self.engineAI == "lungmask R231":
                    self.showStatusMessage('Creating lungs with lungmask AI ...')
                    model = mask.get_model('unet','R231')
                    segmentation_np = mask.apply(inputVolumeSitk, model)
                    
                    # add lung segments
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "right lung", 1, self.inputVolume, self.rightLungColor)
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "left lung", 2, self.inputVolume, self.leftLungColor)
                    # Postprocess lungs 
                    self.postprocessSegment(self.outputSegmentation,0,"right lung")
                    self.postprocessSegment(self.outputSegmentation,1,"left lung")
                elif self.engineAI == "lungmask LTRCLobes":
                    self.showStatusMessage('Creating lungs and lobes with lungmask AI ...')
                    model = mask.get_model('unet','LTRCLobes')
                    segmentation_np = mask.apply(inputVolumeSitk, model)
                    # add lobe segments
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "left upper lobe", 1, self.inputVolume, self.leftUpperLobeColor)
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "left lower lobe", 2, self.inputVolume, self.leftLowerLobeColor)
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "right upper lobe", 3, self.inputVolume, self.rightUpperLobeColor)
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "right middle lobe", 4, self.inputVolume, self.rightMiddleLobeColor)
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "right lower lobe", 5, self.inputVolume, self.rightLowerLobeColor)                    
                    # Postprocess lobes
                    self.postprocessSegment(self.outputSegmentation,0,"left upper lobe")
                    self.postprocessSegment(self.outputSegmentation,1,"left lower lobe")
                    self.postprocessSegment(self.outputSegmentation,2,"right upper lobe")
                    self.postprocessSegment(self.outputSegmentation,3,"right middle lobe")
                    self.postprocessSegment(self.outputSegmentation,4,"right lower lobe")
                elif self.engineAI == "lungmask LTRCLobes_R231":
                    self.showStatusMessage('Creating lungs and lobes with lungmask AI ...')
                    segmentation_np = mask.apply_fused(inputVolumeSitk)
                    # add lobe segments
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "left upper lobe", 1, self.inputVolume, self.leftUpperLobeColor)
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "left lower lobe", 2, self.inputVolume, self.leftLowerLobeColor)
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "right upper lobe", 3, self.inputVolume, self.rightUpperLobeColor)
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "right middle lobe", 4, self.inputVolume, self.rightMiddleLobeColor)
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "right lower lobe", 5, self.inputVolume, self.rightLowerLobeColor)                    
                    # Postprocess lobes
                    self.postprocessSegment(self.outputSegmentation,0,"left upper lobe")
                    self.postprocessSegment(self.outputSegmentation,1,"left lower lobe")
                    self.postprocessSegment(self.outputSegmentation,2,"right upper lobe")
                    self.postprocessSegment(self.outputSegmentation,3,"right middle lobe")
                    self.postprocessSegment(self.outputSegmentation,4,"right lower lobe")
                elif self.engineAI == "lungmask R231CovidWeb":
                    self.showStatusMessage('Creating lungs with lungmask AI ...')
                    model = mask.get_model('unet','R231CovidWeb')
                    segmentation_np = mask.apply(inputVolumeSitk, model)
                    # add lung segments
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "right lung", 1, self.inputVolume, self.rightLungColor)
                    self.addSegmentFromNumpyArray(self.outputSegmentation, segmentation_np, "left lung", 2, self.inputVolume, self.leftLungColor)
                    # Postprocess lungs 
                    self.postprocessSegment(self.outputSegmentation,0,"right lung")
                    self.postprocessSegment(self.outputSegmentation,1,"left lung")
                else:
                    raise ValueError('This lungmask AI engine model is not supported.')

                
                logging.info("Segmentation done.")

            elif self.engineAI.find("TotalSegmentator") == 0:
                self.showStatusMessage(' Creating segmentations with TotalSegmentator ...')
                tslogic = slicer.util.getModuleLogic('TotalSegmentator')
                if not tslogic: 
                    raise RuntimeError("TotalSegmentator program logic not found - please install the TotalSegmentator extension.")

                tsOutputSegmentation = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode', 'TotalSegmentator')
                if self.fastOption: 
                    tslogic.process(self.inputVolume, tsOutputSegmentation, True, "total")
                else:
                    tslogic.process(self.inputVolume, tsOutputSegmentation, False, "total")

                if self.engineAI == "TotalSegmentator all" :  
                    # turn on visibility by default
                    tsOutputSegmentation.GetDisplayNode().SetVisibility(True)
                else:
                    # turn off visibility by default
                    tsOutputSegmentation.GetDisplayNode().SetVisibility(False)
                    
                self.importTotalSegmentatorSegment("right upper lobe","lung_upper_lobe_right",self.outputSegmentation, tsOutputSegmentation, self.rightUpperLobeColor)
                self.importTotalSegmentatorSegment("right middle lobe","lung_middle_lobe_right",self.outputSegmentation, tsOutputSegmentation, self.rightMiddleLobeColor)
                self.importTotalSegmentatorSegment("right lower lobe","lung_lower_lobe_right",self.outputSegmentation, tsOutputSegmentation, self.rightLowerLobeColor)
                self.importTotalSegmentatorSegment("left upper lobe","lung_upper_lobe_left",self.outputSegmentation, tsOutputSegmentation, self.leftUpperLobeColor)
                self.importTotalSegmentatorSegment("left lower lobe","lung_lower_lobe_left",self.outputSegmentation, tsOutputSegmentation, self.leftLowerLobeColor)
                self.importTotalSegmentatorSegment("trachea","trachea",self.outputSegmentation, tsOutputSegmentation, self.tracheaColor)
                self.importTotalSegmentatorSegment("pulmonary artery","pulmonary_artery",self.outputSegmentation, tsOutputSegmentation, self.pulmonaryArteryColor)
                self.importTotalSegmentatorSegment("left atrium of heart","heart_atrium_left",self.outputSegmentation,tsOutputSegmentation, self.pulmonaryVeinColor)
                self.importTotalSegmentatorSegment("lung","lung",self.outputSegmentation, tsOutputSegmentation, self.rightLungColor)
                self.importTotalSegmentatorSegment("lung vessels", "lung_vessels",self.outputSegmentation, tsOutputSegmentation, self.vesselMaskColor)
                self.importTotalSegmentatorSegment("airways and bronchi","lung_trachea_bronchia",self.outputSegmentation, tsOutputSegmentation, self.tracheaColor)
                                
                logging.info("Segmentation done.")
                
            elif self.engineAI.find("MONAILabel") == 0:
                self.showStatusMessage(' Creating segmentations with MONAILabel ...')
                logic = slicer.util.getModuleLogic('MONAILabel')
                # connect to server
                try:
                    #check if Monailabel is connected correctly
                    server_add = "http://127.0.0.1:8000"
                    logic.setServer(server_url=server_add)
                    MONAILabelClient = logic.info()
                    print(MONAILabelClient)
                except Exception as e:
                    slicer.util.errorDisplay("Unable to connect to MONAILabel server on http://127.0.0.1:8000"+str(e))
                    import traceback
                    traceback.print_exc()
                else:
                    # save the volume and get the path
                    tempVolDir, image_id, in_file = self.saveVolTemp(self.inputVolume)
                    model = "segmentation_lung"
                    params = {'largest_cc': True}
                    # infer
                    result_file, params = logic.infer(model, in_file, params)
                    # load the autosegmented segmentation file in Slicer
                    tempResultSegmentation = slicer.util.loadSegmentation(result_file)
                    # copy segments to lung segmentation and tag them
                    self.outputSegmentation.GetSegmentation().DeepCopy(tempResultSegmentation.GetSegmentation())
                    segment = self.outputSegmentation.GetSegmentation().GetSegment("Segment_1")
                    segment.SetName("right lung")
                    segID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName("right lung")
                    self.setAnatomicalTag(self.outputSegmentation, "right lung", segID)
                    segment = self.outputSegmentation.GetSegmentation().GetSegment("Segment_2")
                    segment.SetName("left lung")
                    segID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName("left lung")
                    self.setAnatomicalTag(self.outputSegmentation, "left lung", segID)
                    segment = self.outputSegmentation.GetSegmentation().GetSegment("Segment_3")
                    segment.SetName("airways")
                    segID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName("airways")
                    self.setAnatomicalTag(self.outputSegmentation, "airways", segID)
                    # cleanup
                    if os.path.exists(in_file):
                      os.remove(in_file)
                    slicer.mrmlScene.RemoveNode(tempResultSegmentation)
            else:
                logging.info("No AI engine defined.")  
        
        if self.detailedAirways:
            segID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName("other")
            if segID: 
                self.outputSegmentation.GetSegmentation().RemoveSegment(segID)
            
            airwaySegID = self.addSegment(self.outputSegmentation, "airways", self.tracheaColor)

            if not self.segmentEditorWidget.effectByName("Local Threshold"):
                slicer.util.errorDisplay("Please install 'SegmentEditorExtraEffects' extension using Extension Manager.")
            else:
                self.showStatusMessage('Airway segmentation ...')
                self.segmentEditorNode = self.segmentEditorWidget.mrmlSegmentEditorNode()
                self.outputSegmentation.SetReferenceImageGeometryParameterFromVolumeNode(self.inputVolume)
                wasModified = self.outputSegmentation.StartModify()
                self.segmentEditorWidget.setSourceVolumeNode(self.inputVolume)
                # Trigger display update
                self.outputSegmentation.Modified()
                self.outputSegmentation.EndModify(wasModified)

                self.segmentEditorNode.SetSelectedSegmentID("airways")
                self.segmentEditorWidget.setActiveEffectByName("Local Threshold")
                effect = self.segmentEditorWidget.activeEffect()
                
                effect.setParameter("AutoThresholdMethod","OTSU")
                effect.setParameter("AutoThresholdMode","SET_MIN_UPPER")
                effect.setParameter("BrushType","CIRCLE")
                effect.setParameter("FeatureSizeMm:","3")
                effect.setParameter("HistogramSetLower","LOWER")
                effect.setParameter("HistogramSetUpper","UPPER")
                effect.setParameter("MaximumThreshold",self.airwayThresholdMax)
                effect.setParameter("MinimumThreshold",self.airwayThresholdMin)
                                
                if self.airwaySegmentationDetailLevel == "low detail":
                    effect.setParameter("MinimumDiameterMm","3")
                elif self.airwaySegmentationDetailLevel == "medium detail":
                    effect.setParameter("MinimumDiameterMm","2")
                elif self.airwaySegmentationDetailLevel == "high detail":
                    effect.setParameter("MinimumDiameterMm","1")
                    
                effect.setParameter("SegmentationAlgorithm","GrowCut")
                # do not modify lungs by airways to avoid postprocessing (tumor-like) effects on lung mask
                self.segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone) 
                self.segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)
                import numpy as np
                markupsIndex = 0
                
                # Get point coordinate in RAS
                point_Ras = [0, 0, 0, 1]
                self.tracheaFiducials.GetNthFiducialWorldCoordinates(markupsIndex, point_Ras)
                
                # If volume node is transformed, apply that transform to get volume's RAS coordinates
                transformRasToVolumeRas = vtk.vtkGeneralTransform()
                slicer.vtkMRMLTransformNode.GetTransformBetweenNodes(None, self.inputVolume.GetParentTransformNode(), transformRasToVolumeRas)
                point_VolumeRas = transformRasToVolumeRas.TransformPoint(point_Ras[0:3])

                # Get voxel coordinates from physical coordinates
                volumeRasToIjk = vtk.vtkMatrix4x4()
                self.inputVolume.GetRASToIJKMatrix(volumeRasToIjk)
                point_Ijk = [0, 0, 0, 1]
                volumeRasToIjk.MultiplyPoint(np.append(point_VolumeRas,1.0), point_Ijk)
                point_Ijk = [ int(round(c)) for c in point_Ijk[0:3] ]

                # Print output
                print("IJK trachea markup")
                print(point_Ijk)

                ijkPoints = vtk.vtkPoints()
                #ijkPoints.InsertNextPoint(pos[0],pos[1],pos[2])
                ijkPoints.InsertNextPoint(point_Ijk[0],point_Ijk[1],point_Ijk[2])

                effect.self().apply(ijkPoints)
                
                self.showStatusMessage(f'Filling holes in airways ...')
                self.segmentEditorNode.SetSelectedSegmentID("airways")
                self.segmentEditorWidget.setActiveEffectByName("Smoothing")
                effect = self.segmentEditorWidget.activeEffect()
                effect.setParameter("SmoothingMethod","MORPHOLOGICAL_CLOSING")
                effect.setParameter("KernelSizeMm","3")
                effect.setParameter("ApplyToAllVisibleSegments","0")
                effect.setParameter("ColorSmudge","0")
                effect.setParameter("EraseAllSegments","0")
                effect.setParameter("GaussianStandardDeviationMm","3")
                effect.setParameter("JointTaubinSmoothingFactor","0.5")
                effect.self().onApply()
                
            segment = self.outputSegmentation.GetSegmentation().GetSegment(airwaySegID)
            segment.SetTag(segment.GetTerminologyEntryTagName(),
              "Segmentation category and type - 3D Slicer General Anatomy list"
              "~SCT^123037004^Anatomical Structure"
              "~SCT^44567001^Trachea"
              "~^^"
              "~Anatomic codes - DICOM master list"
              "~^^"
              "~^^")
            
        # create segments for both lungs, vessel and tumor segmentation
        vesselMaskID = self.addSegment(self.outputSegmentation, "vesselmask", self.vesselmaskColor, 1.0)
        self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(vesselMaskID,False)
        PASegmentID = self.addSegment(self.outputSegmentation, "PA", self.PAColor, 1.0)
        self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(PASegmentID,False)
        PVSegmentID = self.addSegment(self.outputSegmentation, "PV", self.PVColor, 1.0)
        self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(PVSegmentID,False)
        tumorSegmentID = self.addSegment(self.outputSegmentation, "tumor", self.tumorColor, 1.0)
        self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(tumorSegmentID,False)
        thoracicCavityID = self.addSegment(self.outputSegmentation, "thoracic cavity", self.thoracicCavityColor, 0.3)
        self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(thoracicCavityID,False)
        lungsID = self.addSegment(self.outputSegmentation, "lungs", self.rightLungColor, 0.3)
        self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(lungsID,False)

        self.segmentEditorWidget.mrmlSegmentEditorNode().SetMasterVolumeIntensityMask(False)
        intensityRange = [0,0]
        self.segmentEditorWidget.mrmlSegmentEditorNode().SetSourceVolumeIntensityMaskRange(intensityRange)
        self.segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone) 
        self.segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)

        # AI created lobes only, so create lungs and add lobes 
        if not self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName("right lung"): 
            rightLungID = self.addSegment(self.outputSegmentation, "right lung", self.rightLungColor, 0.3)
            self.addSegmentToSegment(self.outputSegmentation, "right upper lobe", "right lung")
            self.addSegmentToSegment(self.outputSegmentation, "right middle lobe", "right lung")
            self.addSegmentToSegment(self.outputSegmentation, "right lower lobe", "right lung")

        if not self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName("left lung"): 
            leftLungID = self.addSegment(self.outputSegmentation, "left lung", self.leftLungColor, 0.3)
            self.addSegmentToSegment(self.outputSegmentation, "left upper lobe", "left lung")
            self.addSegmentToSegment(self.outputSegmentation, "left lower lobe", "left lung")

 
        self.addSegmentToSegment(self.outputSegmentation, "right lung", "thoracic cavity")
        self.addSegmentToSegment(self.outputSegmentation, "left lung", "thoracic cavity")
    
        self.addSegmentToSegment(self.outputSegmentation, "right lung", "lungs")
        self.addSegmentToSegment(self.outputSegmentation, "left lung", "lungs")

        self.maskedVolume = None
        if self.createVessels:
            if not self.segmentEditorWidget.effectByName("Wrap Solidify"):
                slicer.util.errorDisplay("Please install 'Wrap Solidify' extension using Extension Manager.")
            else:
                # Create thoracic cavity from lung segmentations
                self.showStatusMessage('Creating thoracic cavity segment with wrap solidify effect ...')
                self.segmentEditorNode.SetSelectedSegmentID(thoracicCavityID)
                
                self.segmentEditorWidget.setActiveEffectByName("Wrap Solidify")
                effect = self.segmentEditorWidget.activeEffect()
                effect.setParameter("carveHolesInOuterSurface","False")
                effect.setParameter("carveHolesInOuterSurfaceDiameter","10")
                effect.setParameter("createShell","False")
                effect.setParameter("outputType","segment")
                effect.setParameter("preserveCracks","True")
                effect.setParameter("region","outerSurface")
                effect.setParameter("regionSegmentID","thoracic cavity")
                effect.setParameter("remeshOversampling","1.5")
                effect.setParameter("saveIntermediateResults","False")
                effect.setParameter("shellOffsetDirection","inside")
                effect.setParameter("shellThickness","1.5")
                effect.setParameter("shrinkwrapIterations","6")
                effect.setParameter("smoothingFactor","0.2")
                effect.setParameter("splitCavities","False")
                effect.setParameter("splitCavitiesDiameter","5")
                effect.self().onApply()
                                
                # Create vessel mask
                self.segmentEditorWidget.setSegmentationNode(self.outputSegmentation)
                self.segmentEditorWidget.setSourceVolumeNode(self.inputVolume)

                self.segmentEditorWidget.mrmlSegmentEditorNode().SetMasterVolumeIntensityMask(False)
                intensityRange = [self.vesselThresholdMin, self.vesselThresholdMax]
                self.segmentEditorWidget.mrmlSegmentEditorNode().SetSourceVolumeIntensityMaskRange(intensityRange)

                self.segmentEditorNode.SetSelectedSegmentID(vesselMaskID)
                self.segmentEditorNode.SetMaskSegmentID(thoracicCavityID)
                self.segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone) 
                self.segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedInsideSingleSegment)

                self.showStatusMessage('Creating vessel mask with threshold effect ...')
                self.segmentEditorWidget.setActiveEffectByName("Threshold")
                effect = self.segmentEditorWidget.activeEffect()
                effect.setParameter("AutoThresholdMethod","OTSU")
                effect.setParameter("AutoThresholdMode","SET_LOWER_MAX")
                effect.setParameter("BrushType","CIRCLE")
                effect.setParameter("HistogramSetLower","LOWER")
                effect.setParameter("HistogramSetUpper","UPPER")
                effect.setParameter("MaximumThreshold",self.vesselThresholdMax)
                effect.setParameter("MinimumThreshold",self.vesselThresholdMin)
                effect.self().onApply()

                self.showStatusMessage(f'Filling holes in vessel mask ...')
                self.segmentEditorNode.SetSelectedSegmentID("vesselmask")
                self.segmentEditorWidget.setActiveEffectByName("Smoothing")
                effect = self.segmentEditorWidget.activeEffect()
                effect.setParameter("SmoothingMethod","MORPHOLOGICAL_CLOSING")
                effect.setParameter("KernelSizeMm","3")
                effect.setParameter("ApplyToAllVisibleSegments","0")
                effect.setParameter("ColorSmudge","0")
                effect.setParameter("EraseAllSegments","0")
                effect.setParameter("GaussianStandardDeviationMm","3")
                effect.setParameter("JointTaubinSmoothingFactor","0.5")
                effect.self().onApply()
                
                self.segmentEditorWidget.setSegmentationNode(self.outputSegmentation)
                self.segmentEditorWidget.setSourceVolumeNode(self.inputVolume)

                # Create masked volume 
                self.segmentEditorNode.SetSelectedSegmentID(thoracicCavityID)
                self.segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone) 
                self.segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)
                self.maskedVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", self.inputVolume.GetName() + f" masked volume")


                self.showStatusMessage('Creating thoracic cavity volume with mask volume effect ...')
                self.segmentEditorWidget.setActiveEffectByName("Mask volume")
                effect = self.segmentEditorWidget.activeEffect()
                effect.setParameter("BinaryMaskFillValueInside","1")
                effect.setParameter("BinaryMaskFillValueOutside","0")
                effect.setParameter("FillValue","0")
                effect.setParameter("InputVisibility","True")
                effect.setParameter("Operation","FILL_OUTSIDE")
                effect.self().outputVolumeSelector.setCurrentNode(self.maskedVolume)
                effect.self().onApply()
                self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(vesselMaskID,True)

        # Use a lower smoothing then the default 0.5 to ensure that thin airways are not suppressed in the 3D output
        self.outputSegmentation.GetSegmentation().SetConversionParameter("Smoothing factor","0.3")
                        
        self.outputSegmentation.GetDisplayNode().SetVisibility(True)

        self.showStatusMessage(' Creating 3D ...')
        self.outputSegmentation.CreateClosedSurfaceRepresentation()
        # center 3D view
        layoutManager = slicer.app.layoutManager()
        threeDWidget = layoutManager.threeDWidget(0)
        threeDView = threeDWidget.threeDView()
        threeDView.resetFocalPoint()

        # Do not show lungs when in AI mode when have lobes
        if self.useAI: 
            if self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName("right upper lobe"):
                segmentation = self.outputSegmentation.GetSegmentation()
                rightLungID = segmentation.GetSegmentIdBySegmentName("right lung")
                self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(rightLungID,False)
                leftLungID = segmentation.GetSegmentIdBySegmentName("left lung")
                self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(leftLungID,False)
                lungID = segmentation.GetSegmentIdBySegmentName("lung")
                self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(lungID,False)
                
        # Never show both lungs initially 
        segmentation = self.outputSegmentation.GetSegmentation()
        lungsID = segmentation.GetSegmentIdBySegmentName("lungs")
        self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(lungsID,False)

        # Restore confirmation popup setting for editing a hidden segment
        if not self.useAI: 
            slicer.app.settings().setValue("Segmentations/ConfirmEditHiddenSegment", previousConfirmEditHiddenSegmentSetting)

        slicer.mrmlScene.RemoveNode(self.rightLungFiducials)
        slicer.mrmlScene.RemoveNode(self.leftLungFiducials)
        slicer.mrmlScene.RemoveNode(self.tracheaFiducials)

        self.showStatusMessage(' Cleaning up ...')
        self.removeTemporaryObjects()

        self.segmentationStarted = False
        self.segmentationFinished = True

        stopTime = time.time()
        logging.info('ApplySegmentation completed in {0:.2f} seconds'.format(stopTime-startTime))


#
# LungCTSegmenterTest
#

class LungCTSegmenterTest(ScriptedLoadableModuleTest):
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
        self.test_LungCTSegmenterNormal()
        slicer.mrmlScene.Clear(0)
        self.test_LungCTSegmenterLungmaskAI()

    def test_LungCTSegmenterNormal(self):
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
        #registerSampleData()
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
        markupsRightLungNode.SetName("R")
        markupsLeftLungNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsLeftLungNode.SetName("L")
        markupsTracheaNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsTracheaNode.SetName("T")

        # add six fiducials each right and left
        markupsRightLungNode.CreateDefaultDisplayNodes()
        markupsRightLungNode.AddFiducial(50.,48.,-173.)
        markupsRightLungNode.AddFiducial(96.,-2.,-173.)
        markupsRightLungNode.AddFiducial(92.,-47.,-173.)
        markupsRightLungNode.AddFiducial(47.,-22.,-52.)
        markupsRightLungNode.AddFiducial(86.,-22.,-128.)
        markupsRightLungNode.AddFiducial(104.,-22.,-189.)
        
        markupsLeftLungNode.CreateDefaultDisplayNodes()
        markupsLeftLungNode.AddFiducial(-100.,29.,-173.)
        markupsLeftLungNode.AddFiducial(-111.,-37.,-173.)
        markupsLeftLungNode.AddFiducial(-76.,-85.,-173.)
        markupsLeftLungNode.AddFiducial(-77.,22.,-55.)
        markupsLeftLungNode.AddFiducial(-100.,-22.,-123.)
        markupsLeftLungNode.AddFiducial(-119.,-22.,-127.)

        # add one fiducial 
        markupsTracheaNode.CreateDefaultDisplayNodes()
        markupsTracheaNode.AddFiducial(-4.,-14.,-90.)

        # Test the module logic

        logic = LungCTSegmenterLogic()

        # Test algorithm 
        self.delayDisplay("Processing, please wait ...")

        logic.removeTemporaryObjects()
        logic.rightLungFiducials = markupsRightLungNode
        logic.leftLungFiducials = markupsLeftLungNode
        logic.tracheaFiducials = markupsTracheaNode
        
        logic.startSegmentation()
        logic.updateSegmentation()
        logic.applySegmentation()
        
        #logic.process(inputVolume, -1000.,-200.,False)
        resultsTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', '_maskResultsTable')

        # Compute stats
        import SegmentStatistics
        
        segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
       
        segStatLogic.getParameterNode().SetParameter("Segmentation", logic.outputSegmentation.GetID())
        segStatLogic.getParameterNode().SetParameter("ScalarVolume", logic.inputVolume.GetID())
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled", "True")
        segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.voxel_count.enabled", "False")
        segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.volume_mm3.enabled", "False")
        segStatLogic.computeStatistics()
        segStatLogic.exportToTable(resultsTableNode)

        #resultsTableNode = slicer.util.getNode('_maskResultsTable')
        _volumeRightLungMask = round(float(resultsTableNode.GetCellText(0,3)))
        _volumeLeftLungMask = round(float(resultsTableNode.GetCellText(1,3)))
        print(_volumeRightLungMask)
        print(_volumeLeftLungMask)
        # assert vs known volumes of the chest CT dataset
        self.assertEqual(_volumeRightLungMask, 3227) 
        self.assertEqual(_volumeLeftLungMask, 3138)


        self.delayDisplay('Test passed')


    def test_LungCTSegmenterLungmaskAI(self):
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
        #registerSampleData()
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
        # Create new marker
        markupsTracheaNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsTracheaNode.SetName("T")

        # add one fiducial 
        markupsTracheaNode.CreateDefaultDisplayNodes()
        markupsTracheaNode.AddFiducial(-4.,-14.,-90.)

        # Test the module logic

        logic = LungCTSegmenterLogic()

        # Test algorithm 
        self.delayDisplay("Processing, please wait ...")

        logic.removeTemporaryObjects()
        logic.tracheaFiducials = markupsTracheaNode
        logic.detailedAirways = False
        logic.createVessels = False
        
        logic.useAI = True
        logic.engineAI = "lungmask LTRCLobes"

        logic.startSegmentation()
        logic.updateSegmentation()
        logic.applySegmentation()
        
        #logic.process(inputVolume, -1000.,-200.,False)
        resultsTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', '_maskResultsTable')

        # Compute stats
        import SegmentStatistics
        
        segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
       
        segStatLogic.getParameterNode().SetParameter("Segmentation", logic.outputSegmentation.GetID())
        segStatLogic.getParameterNode().SetParameter("ScalarVolume", logic.inputVolume.GetID())
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled", "True")
        segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.voxel_count.enabled", "False")
        segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.volume_mm3.enabled", "False")
        segStatLogic.computeStatistics()
        segStatLogic.exportToTable(resultsTableNode)

        #resultsTableNode = slicer.util.getNode('_maskResultsTable')
        _volumeLeftUpperLobe = round(float(resultsTableNode.GetCellText(0,3)))
        _volumeLeftLowerLobe = round(float(resultsTableNode.GetCellText(1,3)))
        _volumeRightUpperLobe = round(float(resultsTableNode.GetCellText(2,3)))
        _volumeRightMiddleLobe = round(float(resultsTableNode.GetCellText(3,3)))
        _volumeRightLowerLobe = round(float(resultsTableNode.GetCellText(4,3)))
        # assert vs known volumes of lobes from the chest CT dataset
        self.assertEqual(_volumeLeftUpperLobe, 1472) 
        self.assertEqual(_volumeLeftLowerLobe, 1658)
        self.assertEqual(_volumeRightUpperLobe, 1424)
        self.assertEqual(_volumeRightMiddleLobe, 493)
        self.assertEqual(_volumeRightLowerLobe, 1308)


        self.delayDisplay('Test passed')
