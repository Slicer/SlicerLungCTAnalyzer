import os
import requests
import unittest
import glob
import time
import logging
import vtk, qt, ctk, slicer
import sys, subprocess
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from SegmentStatisticsPlugins import *

#
# LungCTAnalyzer
#

class LungCTAnalyzer(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Lung CT Analyzer"
        self.parent.categories = ["Chest Imaging Platform"]
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Rudolf Bumm (KSGR Switzerland)"]
        self.parent.helpText = """Lung analysis consists of producing five different segmentations of lungs based on Hounsfield unit range:
Bulla / emphysema, inflated lung, infiltrated llung, collapsed lung and thoracic vessels. It allows a volume quantification
as well as a spacial representation of the diseased lung regions. Furthermore, we introduce a new parameter - CovidQ -
for an instant estimation of the severity of  infestation. See more information in <a href="https://github.com/Slicer/SlicerLungCTAnalyzer">module documentation</a>.<br>
The extension transmits basic information when you use it (simple usage counter). No IP or any personal data are being sent.  

"""
        self.parent.acknowledgementText = """
The first version of this file was originally developed by Rudolf Bumm, Kantonsspital Graubünden, Switzerland. Parts of this code were inspired by a code snippet (https://gist.github.com/lassoan/5ad51c89521d3cd9c5faf65767506b37) of Andras Lasso, PerkLab.
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
        uris='https://github.com/Slicer/SlicerLungCTAnalyzer/releases/download/SampleData/LungCTAnalyzerChestCT.nrrd',
        fileNames='DemoChestCT.nrrd',
        nodeNames='DemoChestCT',
        thumbnailFileName=os.path.join(iconsPath, 'DemoChestCT.png'),
        loadFileType='VolumeFile',
        checksums='SHA256:9bb74f4383bce0ced80243916e785ce564cc2c8f535e8273da8a04f80dff4287'
        )
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        category="Lung",
        sampleName='DemoLungMasks',
        uris='https://github.com/Slicer/SlicerLungCTAnalyzer/releases/download/SampleData/LungCTAnalyzerMaskSegmentation.seg.nrrd',
        fileNames='DemoLungMasks.seg.nrrd',
        nodeNames='DemoLungMasks',
        thumbnailFileName=os.path.join(iconsPath, 'DemoLungMasks.png'),
        loadFileType='SegmentationFile',
        checksums='SHA256:79f151b42cf999c1ecf13ee793da6cf649b54fe8634ec07723e4a1f44e53b57c'
        )

#
# LungCTAnalyzerWidget
#

class LungCTAnalyzerWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        self.version = 2.69
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._updatingGUIFromParameterNode = False
        self.inputFilename = None
        self.batchProcessingInputDir = ""
        self.batchProcessingOutputDir = ""
        self.batchProcessingTestMode = False
        self.batchProcessingIsCancelled = False
        self.csvOnly = False
        self.useCalibratedCT = False
        self.scanInput = False
        self.lobeAnalysis = False
        self.areaAnalysis = False
        self.batchProcessing = False
        self.isNiiGzFormat = False
        self.checkForUpdates = True
        self.resetmode = False
        


    def setup(self):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
       

        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/LungCTAnalyzer.ui'))
        self.layout.addWidget(uiWidget)
        self.layout.objectName = "Lung CT Analyzer layout"
        self.ui = slicer.util.childWidgetVariables(uiWidget)



        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = LungCTAnalyzerLogic()

        self.volumeRenderingPropertyUpdateTimer = qt.QTimer()
        self.volumeRenderingPropertyUpdateTimer.setInterval(1000)
        self.volumeRenderingPropertyUpdateTimer.setSingleShot(True)
        self.volumeRenderingPropertyUpdateTimer.timeout.connect(self.updateVolumeRenderingProperty)

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # These connections ensure that we update the GUI when scene is imported
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndImportEvent, self.onSceneEndImport)

        # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
        # (in the selected parameter node).

        # Input image and segmentation
        self.ui.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.inputSegmentationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onInputSegmentationSelected)
        self.ui.toggleInputSegmentationVisibility2DPushButton.connect('clicked()', self.onToggleInputSegmentationVisibility2D)
        self.ui.toggleInputSegmentationVisibility3DPushButton.connect('clicked()', self.onToggleInputSegmentationVisibility3D)

        # Output options
        self.ui.generateStatisticsCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.lobeAnalysisCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.areaAnalysisCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.niigzFormatCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)

        self.ui.lungMaskedVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.outputSegmentationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.outputResultsTableSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.volumeRenderingPropertyNodeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.testModeCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.csvOnlyCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.useCalibratedCTCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.scanInputCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)

        # Advanced options
        self.ui.checkForUpdatesCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)

        # Thresholds
        self.ui.BullaRangeWidget.connect('valuesChanged(double,double)', self.onBullaRangeWidgetChanged)
        self.ui.InflatedRangeWidget.connect('valuesChanged(double,double)', self.onInflatedRangeWidgetChanged)
        self.ui.InfiltratedRangeWidget.connect('valuesChanged(double,double)', self.onInfiltratedRangeWidgetChanged)
        self.ui.CollapsedRangeWidget.connect('valuesChanged(double,double)', self.onCollapsedRangeWidgetChanged)
        self.ui.VesselsRangeWidget.connect('valuesChanged(double,double)', self.onVesselsRangeWidgetChanged)
        self.ui.restoreDefaultsButton.connect('clicked(bool)', self.onRestoreDefaultsButton)
        self.ui.saveThresholdsButton.connect('clicked(bool)', self.onSaveThresholdsButton)
        self.ui.loadThresholdsButton.connect('clicked(bool)', self.onLoadThresholdsButton)
        self.ui.createPDFReportButton.connect('clicked(bool)', self.onCreatePDFReportButton)
        
        # Connect path selectors
        self.ui.inputDirectoryPathLineEdit.connect('currentPathChanged(const QString&)', self.onInputDirectoryPathLineEditChanged)
        self.ui.outputDirectoryPathLineEdit.connect('currentPathChanged(const QString&)', self.onOutputDirectoryPathLineEditChanged)
        
        self.ui.batchProcessingButton.connect('clicked(bool)', self.onBatchProcessingButton)
        self.ui.cancelBatchProcessingButton.connect('clicked(bool)', self.onCancelBatchProcessingButton)
          
        # Report Dir
       
        self.ui.selectReportDirectoryButton.connect('clicked(bool)', self.onSelectReportDirectoryButton)
        self.ui.selectReportDirectoryButton.directoryChanged.connect(self.onReportDirectoryChanged)
        self.ui.selectReportDirectoryButton.connect('clicked(bool)', self.onSelectReportDirectoryButton)
        self.ui.openReportDirectoryButton.connect('clicked(bool)', self.onOpenReportDirectoryButton)

        settings=qt.QSettings(slicer.app.launcherSettingsFilePath, qt.QSettings.IniFormat)

        self.ui.inputDirectoryPathLineEdit.currentPath = settings.value("LungCtAnalyzer/batchProcessingInputFolder", "")      
        self.ui.outputDirectoryPathLineEdit.currentPath = settings.value("LungCtAnalyzer/batchProcessingOutputFolder", "")

        if settings.value("LungCtAnalyzer/BullaRangeWidgetMinimumValue", "") != "":               
            self.ui.BullaRangeWidget.minimumValue =  float(settings.value("LungCtAnalyzer/BullaRangeWidgetMinimumValue", ""))
        if settings.value("LungCtAnalyzer/BullaRangeMaximumValue", "") != "":               
            self.ui.BullaRangeWidget.maximumValue =  float(settings.value("LungCtAnalyzer/BullaRangeWidgetMaximumValue", ""))

        if settings.value("LungCtAnalyzer/InflatedRangeWidgetMinimumValue", "") != "":               
            self.ui.InflatedRangeWidget.minimumValue =  float(settings.value("LungCtAnalyzer/InflatedRangeWidgetMinimumValue", ""))
        if settings.value("LungCtAnalyzer/InflatedRangeMaximumValue", "") != "":               
            self.ui.InflatedRangeWidget.maximumValue =  float(settings.value("LungCtAnalyzer/InflatedRangeWidgetMaximumValue", ""))

        if settings.value("LungCtAnalyzer/InfiltratedRangeWidgetMinimumValue", "") != "":               
            self.ui.InfiltratedRangeWidget.minimumValue =  float(settings.value("LungCtAnalyzer/InfiltratedRangeWidgetMinimumValue", ""))
        if settings.value("LungCtAnalyzer/InfiltratedRangeMaximumValue", "") != "":               
            self.ui.InfiltratedRangeWidget.maximumValue =  float(settings.value("LungCtAnalyzer/InfiltratedRangeWidgetMaximumValue", ""))

        if settings.value("LungCtAnalyzer/CollapsedRangeWidgetMinimumValue", "") != "":               
            self.ui.CollapsedRangeWidget.minimumValue =  float(settings.value("LungCtAnalyzer/CollapsedRangeWidgetMinimumValue", ""))
        if settings.value("LungCtAnalyzer/CollapsedRangeMaximumValue", "") != "":               
            self.ui.CollapsedRangeWidget.maximumValue =  float(settings.value("LungCtAnalyzer/CollapsedRangeWidgetMaximumValue", ""))

        if settings.value("LungCtAnalyzer/VesselsRangeWidgetMinimumValue", "") != "":               
            self.ui.VesselsRangeWidget.minimumValue =  float(settings.value("LungCtAnalyzer/VesselsRangeWidgetMinimumValue", ""))
        if settings.value("LungCtAnalyzer/VesselsRangeMaximumValue", "") != "":               
            self.ui.VesselsRangeWidget.maximumValue =  float(settings.value("LungCtAnalyzer/VesselsRangeWidgetMaximumValue", ""))
         
        if settings.value("LungCtAnalyzer/testModeCheckBoxChecked", "") != "":               
            self.batchProcessingTestMode = eval(settings.value("LungCtAnalyzer/testModeCheckBoxChecked", ""))
            self.ui.testModeCheckBox.checked = eval(settings.value("LungCtAnalyzer/testModeCheckBoxChecked", ""))

        if settings.value("LungCtAnalyzer/csvOnlyCheckBoxChecked", "") != "":               
            self.csvOnly = eval(settings.value("LungCtAnalyzer/csvOnlyCheckBoxChecked", ""))
            self.ui.csvOnlyCheckBox.checked = eval(settings.value("LungCtAnalyzer/csvOnlyCheckBoxChecked", ""))
       
        if settings.value("LungCtAnalyzer/useCalibratedCTCheckBoxChecked", "") != "":               
            self.useCalibratedCT = eval(settings.value("LungCtAnalyzer/useCalibratedCTCheckBoxChecked", ""))
            self.ui.useCalibratedCTCheckBox.checked = eval(settings.value("LungCtAnalyzer/useCalibratedCTCheckBoxChecked", ""))

        if settings.value("LungCtAnalyzer/scanInputCheckBoxChecked", "") != "":               
            self.scanInput = eval(settings.value("LungCtAnalyzer/scanInputCheckBoxChecked", ""))
            self.ui.scanInputCheckBox.checked = eval(settings.value("LungCtAnalyzer/scanInputCheckBoxChecked", ""))

        if settings.value("LungCtAnalyzer/lobeAnalysisCheckBoxChecked", "") != "":               
            self.lobeAnalysis = eval(settings.value("LungCtAnalyzer/lobeAnalysisCheckBoxChecked", ""))
            self.ui.lobeAnalysisCheckBox.checked = eval(settings.value("LungCtAnalyzer/lobeAnalysisCheckBoxChecked", ""))

        if settings.value("LungCtAnalyzer/areaAnalysisCheckBoxChecked", "") != "":               
            self.areaAnalysis = eval(settings.value("LungCtAnalyzer/areaAnalysisCheckBoxChecked", ""))
            self.ui.areaAnalysisCheckBox.checked = eval(settings.value("LungCtAnalyzer/areaAnalysisCheckBoxChecked", ""))

        if settings.value("LungCtAnalyzer/niigzFormatCheckBoxChecked", "") != "":
            self.isNiiGzFormat = eval(settings.value("LungCtAnalyzer/niigzFormatCheckBoxChecked", ""))
            self.ui.niigzFormatCheckBox.checked = eval(settings.value("LungCtAnalyzer/niigzFormatCheckBoxChecked", ""))

        
        # Opacities
        self.opacitySliders = {
            "Emphysema": self.ui.bullaOpacityWidget,
            "Inflated": self.ui.infiltratedOpacityWidget,
            "Infiltration": self.ui.infiltratedOpacityWidget,
            "Collapsed": self.ui.collapsedOpacityWidget,
            "Vessels": self.ui.vesselsOpacityWidget,
            }
        for segment in self.opacitySliders:
            self.opacitySliders[segment].connect('valueChanged(double)', self.updateVolumeRenderingPropertyFromGUI)


        # Buttons
        self.ui.downloadCovidDataButton.connect('clicked()', self.onDownloadCovidData)
        self.ui.applyButton.connect('clicked()', self.onApplyButton)
        self.ui.showResultsTablePushButton.connect('clicked()', self.onShowResultsTable)
        self.ui.saveResultsCSVButton.connect('clicked()', self.onSaveResultsCSV)
        self.ui.showCovidResultsTableButton.connect('clicked()', self.onShowCovidResultsTable)
        self.ui.showEmphysemaResultsTableButton.connect('clicked()', self.onShowEmphysemaResultsTable)
        self.ui.toggleOutputSegmentationVisibility2DPushButton.connect('clicked()', self.onToggleOutputSegmentationVisibility2D)
        self.ui.toggleOutputSegmentationVisibility3DPushButton.connect('clicked()', self.onToggleOutputSegmentationVisibility3D)
        self.ui.toggleMaskedVolumeDisplay2DPushButton.connect('clicked()', self.onMaskedVolumeDisplay2D)
        self.ui.toggleMaskedVolumeDisplay3DPushButton.connect('clicked()', self.onMaskedVolumeDisplay3D)        

        self.reportFolder = ""

        import configparser
        parser = configparser.SafeConfigParser()
        parser.read(slicer.app.slicerUserSettingsFilePath + 'LCTA.INI')
        if parser.has_option('reportFolder', 'path'): 
            self.reportFolder = parser.get('reportFolder','path')
        else: 
            self.reportFolder = f"{slicer.app.defaultScenePath}/LungCTAnalyzerReports/"
            from pathlib import Path
            Path(self.reportFolder).mkdir(parents=True, exist_ok=True)
            parser.add_section('reportFolder')
            parser.set('reportFolder', 'path', self.reportFolder)
            with open(slicer.app.slicerUserSettingsFilePath + 'LCTA.INI', 'w') as configfile:    # save
                parser.write(configfile)

        self.ui.selectReportDirectoryButton.directory = self.reportFolder

        if parser.has_option('Updates', 'check'): 
            self.checkForUpdates = parser.getboolean('Updates','check')
        else: 
            parser.add_section('Updates')
            parser.set('Updates', 'check', str(True))
            self.checkForUpdates = True
            with open(slicer.app.slicerUserSettingsFilePath + 'LCTA.INI', 'w') as configfile:    # save
                parser.write(configfile)


        # Make sure parameter node is initialized (needed for module reload)
        self.logic.inputSegmentation = None
        self.logic.inputVolume = None
        self.initializeParameterNode()
        slicer.app.applicationLogic().FitSliceToAll()
     
        # Set initial button texts
        
        if hasattr(self.logic, "inputSegmentation"):
            if self.logic.inputSegmentation: 
                segmentationDisplayNode = self.logic.inputSegmentation.GetDisplayNode()
                if segmentationDisplayNode.GetVisibility2D():
                    self.ui.toggleInputSegmentationVisibility2DPushButton.text = "Hide mask segments in 2D" 
                else: 
                    self.ui.toggleInputSegmentationVisibility2DPushButton.text = "Show mask segments in 2D" 
                if self.logic.inputSegmentation.GetDisplayNode().GetVisibility3D() and self.logic.inputSegmentation.GetSegmentation().ContainsRepresentation("Closed surface"):
                    self.ui.toggleInputSegmentationVisibility3DPushButton.text = "Hide mask segments in 3D" 
                else: 
                    self.ui.toggleInputSegmentationVisibility3DPushButton.text = "Show mask segments in 3D" 
        else: 
            self.ui.toggleInputSegmentationVisibility2DPushButton.text = "Show mask segments in 2D" 
            self.ui.toggleInputSegmentationVisibility3DPushButton.text = "Show mask segments in 3D" 
        
        if hasattr(self.logic, "outputSegmentation"):
            if self.logic.outputSegmentation: 
                segmentationDisplayNode = self.logic.outputSegmentation.GetDisplayNode()
                if segmentationDisplayNode.GetVisibility2D():
                    self.ui.toggleOutputSegmentationVisibility2DPushButton.text = "Hide output segments in 2D" 
                else: 
                    self.ui.toggleOutputSegmentationVisibility2DPushButton.text = "Show output segments in 2D" 

                if self.logic.outputSegmentation.GetDisplayNode().GetVisibility3D() and self.logic.outputSegmentation.GetSegmentation().ContainsRepresentation("Closed surface"):
                    self.ui.toggleOutputSegmentationVisibility3DPushButton.text = "Hide output segments in 3D" 
                else: 
                    self.ui.toggleOutputSegmentationVisibility3DPushButton.text = "Show output segments in 3D" 
        else: 
            self.ui.toggleOutputSegmentationVisibility2DPushButton.text = "Show output segments in 2D" 
            self.ui.toggleOutputSegmentationVisibility3DPushButton.text = "Show output segments in 3D" 
        
        if hasattr(self.logic, "showLungMaskedVolumeIn2D"):
            if self.logic.showLungMaskedVolumeIn2D:
                self.ui.toggleMaskedVolumeDisplay2DPushButton.text = "Hide preview in 2D" 
            else:
                self.ui.toggleMaskedVolumeDisplay2DPushButton.text = "Show preview in 2D" 
        else: 
            self.ui.toggleMaskedVolumeDisplay2DPushButton.text = "Show preview in 2D" 
        
        if hasattr(self.logic, "wasVisible3D"):
            if self.logic.wasVisible3D: 
                self.ui.toggleMaskedVolumeDisplay3DPushButton.text = "Show preview in 3D"
            else:
                self.ui.toggleMaskedVolumeDisplay3DPushButton.text = "Hide preview in 3D"
        else:  
            self.ui.toggleMaskedVolumeDisplay3DPushButton.text = "Show preview in 3D"
        
        self.show3DWarning = True

        # show version on GUI 
        self.versionText = "Lung CT Analyzer V %.2f" % self.version       
        self.ui.versionLabel.text = self.versionText
        
        # show uses 
        import os
        import requests

        def get_users(program):
            try:
              url = 'http://scientific-networks.de/get_users.php'
              api_key = "WVnB2F7Uibt2TC"
              params = {'api_key': api_key, 'prog': program, 'year': "2023"}
              response = requests.get(url, params=params, timeout=5)
              return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Unable to get users {e}")
            return None  # or some default values
        # use it
        uses = get_users("lcta")
        if uses: 
            usage_text = str(uses) + " uses since 9/23"       
            self.ui.label_uses.text = usage_text
        
        
        
        from urllib.request import urlopen
        import json
        
        if self.checkForUpdates: 
            link = "https://github.com/Slicer/SlicerLungCTAnalyzer/blob/master/version.json?raw=true"
            try:
                f = urlopen(link)
                myfile = f.read()
                #print(myfile)
                dct = json.loads(myfile)
                #print(dct["version"])
                if self.version < float(dct["version"]): 
                    slicer.util.messageBox("There is a new version of Lung CT Analyzer available. \n Please consider updating via the extension manager.")
                else:
                    print("Lung CT analyzer is up to date.")
            except Exception as e:
                qt.QApplication.restoreOverrideCursor()
                slicer.util.errorDisplay("Failed to check current version: "+str(e))
        else : 
            print("Checking of Lung CT analyzer updates is disabled.")
        

        
    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        self.removeObservers()
 
        import configparser
        parser = configparser.SafeConfigParser()
        parser.read(slicer.app.slicerUserSettingsFilePath + 'LCTA.INI')

        if parser.has_option('Updates', 'check'): 
            if self.checkForUpdates: 
                parser.set('Updates','check',str(True))
            else: 
                parser.set('Updates','check',str(False))
        else: 
            parser.add_section('Updates')
            if self.checkForUpdates: 
                parser.set('Updates','check',str(True))
            else: 
                parser.set('Updates','check',str(False))
        with open(slicer.app.slicerUserSettingsFilePath + 'LCTA.INI', 'w') as configfile:    # save
            parser.write(configfile)


    def enter(self):
        """
        Called each time the user opens this module.
        """
        # Make sure parameter node exists and observed
        print("Enter")
        self.initializeParameterNode()
        self.updateParameterNodeFromGUI()


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

    def onSceneEndImport(self, caller, event):
        """
        Called just after the scene is imported
        """
        return
        
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
        # print("initializeParameterNode")
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())       
        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self.logic.inputVolume:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if firstVolumeNode:
                self.logic.inputVolume = firstVolumeNode

        if not self.logic.inputSegmentation:
            segNode = slicer.util.getFirstNodeByClassByName("vtkMRMLSegmentationNode", "Lung segmentation")
            if segNode:
                self.logic.inputSegmentation = segNode
                segmentation = segNode.GetSegmentation()
                self.logic.rightLungMaskSegmentID = segmentation.GetSegmentIdBySegmentName("right lung")
                print("right lung segment exists")
                self.logic.leftLungMaskSegmentID = segmentation.GetSegmentIdBySegmentName("left lung")
                print("left lung segment exists")
                #initial masks always on
                segmentationDisplayNode = self.logic.inputSegmentation.GetDisplayNode()
                segmentationDisplayNode.Visibility2DOn()
                self.ui.toggleInputSegmentationVisibility2DPushButton.text = "Hide mask segments in 2D" 
                segmentationDisplayNode.Visibility3DOff()
                self.ui.toggleInputSegmentationVisibility3DPushButton.text = "Show mask segments in 3D" 
        
        #initial masks always on
        if self.logic.inputSegmentation: 
            segmentationDisplayNode = self.logic.inputSegmentation.GetDisplayNode()
            segmentationDisplayNode.Visibility2DOn()
            self.ui.toggleInputSegmentationVisibility2DPushButton.text = "Hide mask segments in 2D" 
            segmentationDisplayNode.Visibility3DOff()
            self.ui.toggleInputSegmentationVisibility3DPushButton.text = "Show mask segments in 3D" 
            
        if (self.logic.inputVolume and self.logic.inputSegmentation
            and self.logic.rightLungMaskSegmentID and self.logic.leftLungMaskSegmentID):
            self.ui.applyButton.toolTip = "Compute results"
            self.ui.applyButton.enabled = True


    def checkInputVolumeAndSegmentations(self):
        """
        
        """      
        self.logic.inputVolume = self.ui.inputVolumeSelector.currentNode()
        if not self.logic.inputVolume:
            slicer.util.messageBox("No input volume.")
            raise ValueError("No input volume.")
        else: 
            print("self.logic.inputVolume found")

        self.logic.inputSegmentation = self.ui.inputSegmentationSelector.currentNode()
         
        if self.logic.inputSegmentation:
            print("self.logic.inputsegmentation found")
            segmentation = self.logic.inputSegmentation.GetSegmentation()
            self.logic.rightLungMaskSegmentID = segmentation.GetSegmentIdBySegmentName("right lung")
            if not self.logic.rightLungMaskSegmentID: 
                slicer.util.messageBox("right lung input segmentent missing.")
                raise ValueError("Right lung input segment missing.")
            else: 
                print("Right lung input segment found.")
            self.logic.leftLungMaskSegmentID = segmentation.GetSegmentIdBySegmentName("left lung")
            if not self.logic.leftLungMaskSegmentID: 
                slicer.util.messageBox("Left lung input segment missing.")
                raise ValueError("Left lung input segment missing.")
            else: 
                print("Left lung input segment found.")
               
        else: 
            slicer.util.messageBox("Input segmentation missing.")
            raise ValueError("No input segmentation.")

        if self.lobeAnalysis: 
            lobeMissing = False
            for lobeName in ['right upper lobe', 'right middle lobe', 'right lower lobe', 'left upper lobe', 'left lower lobe' ]:
                sourceSegID = self.logic.inputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(lobeName)
                if not sourceSegID: 
                    slicer.util.messageBox(lobeName + " input segment missing. Recreate input segmentation with AI and lobe generation.")
                    lobeMissing = True
                else: 
                    print(lobeName + " input segment found.")
            if lobeMissing:     
                raise ValueError("Lobe input segment is missing.")


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

       #  logging.info("updateGUIFromParameterNode")

        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return

        # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
        self._updatingGUIFromParameterNode = True

        if not self.batchProcessing: 
            thresholds = self.logic.thresholds
            self.ui.BullaRangeWidget.minimumValue = thresholds['thresholdBullaLower']
            self.ui.BullaRangeWidget.maximumValue = thresholds['thresholdBullaInflated']
            self.ui.InflatedRangeWidget.minimumValue = thresholds['thresholdBullaInflated']
            self.ui.InflatedRangeWidget.maximumValue = thresholds['thresholdInflatedInfiltrated']
            self.ui.InfiltratedRangeWidget.minimumValue = thresholds['thresholdInflatedInfiltrated']
            self.ui.InfiltratedRangeWidget.maximumValue = thresholds['thresholdInfiltratedCollapsed']
            self.ui.CollapsedRangeWidget.minimumValue = thresholds['thresholdInfiltratedCollapsed']
            self.ui.CollapsedRangeWidget.maximumValue = thresholds['thresholdCollapsedVessels']
            self.ui.VesselsRangeWidget.minimumValue = thresholds['thresholdCollapsedVessels']
            self.ui.VesselsRangeWidget.maximumValue = thresholds['thresholdVesselsUpper']


        # Update node selectors and sliders
        self.ui.inputVolumeSelector.setCurrentNode(self.logic.inputVolume)
        wasBlocked = self.ui.inputSegmentationSelector.blockSignals(True)
        self.ui.inputSegmentationSelector.setCurrentNode(self.logic.inputSegmentation)
        self.ui.inputSegmentationSelector.blockSignals(wasBlocked)

        self.ui.lungMaskedVolumeSelector.setCurrentNode(self.logic.lungMaskedVolume)
        self.ui.outputSegmentationSelector.setCurrentNode(self.logic.outputSegmentation)
        self.ui.outputResultsTableSelector.setCurrentNode(self.logic.resultsTable)
        self.ui.volumeRenderingPropertyNodeSelector.setCurrentNode(self.logic.volumeRenderingPropertyNode)
        self.ui.selectReportDirectoryButton.directory = self.reportFolder

        self.ui.testModeCheckBox.checked = self.batchProcessingTestMode
        self.ui.csvOnlyCheckBox.checked = self.csvOnly
        self.ui.useCalibratedCTCheckBox.checked = self.useCalibratedCT
        self.ui.scanInputCheckBox.checked = self.scanInput

        self.ui.checkForUpdatesCheckBox.checked = self.checkForUpdates
        self.ui.generateStatisticsCheckBox.checked = self.logic.generateStatistics
        self.ui.lobeAnalysisCheckBox.checked = self.lobeAnalysis
        self.ui.areaAnalysisCheckBox.checked = self.areaAnalysis
        self.ui.niigzFormatCheckBox.checked = self.isNiiGzFormat

        # Update buttons states and tooltips

        self.ui.applyButton.toolTip = "Compute results"
        self.ui.applyButton.enabled = True

        self.ui.createPDFReportButton.enabled = (self.logic.resultsTable is not None)
        self.ui.saveResultsCSVButton.enabled = (self.logic.resultsTable is not None)
        self.ui.showResultsTablePushButton.enabled = (self.logic.resultsTable is not None)
        self.ui.showCovidResultsTableButton.enabled = (self.logic.covidResultsTable is not None)
        self.ui.showEmphysemaResultsTableButton.enabled = (self.logic.emphysemaResultsTable is not None)

        self.ui.toggleInputSegmentationVisibility2DPushButton.enabled = (self.logic.inputSegmentation is not None)
        self.ui.toggleInputSegmentationVisibility3DPushButton.enabled = (self.logic.inputSegmentation is not None)
        self.ui.toggleOutputSegmentationVisibility2DPushButton.enabled = (self.logic.outputSegmentation is not None)
        self.ui.toggleOutputSegmentationVisibility3DPushButton.enabled = (self.logic.outputSegmentation is not None)

        # If thresholds are changed then volume rendering needs an update, too
        self.volumeRenderingPropertyUpdateTimer.start()

        # All the GUI updates are done
        self._updatingGUIFromParameterNode = False

    def updateVolumeRenderingPropertyFromGUI(self):
        self.volumeRenderingPropertyUpdateTimer.start()

    def updateParameterNodeFromGUI(self, caller=None, event=None):
        """
        This method is called when the user makes any change in the GUI.
        The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
        """
        
        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return

        wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

        settings=qt.QSettings(slicer.app.launcherSettingsFilePath, qt.QSettings.IniFormat)
  
        self.logic.inputVolume = self.ui.inputVolumeSelector.currentNode()
        self.logic.inputSegmentation = self.ui.inputSegmentationSelector.currentNode()
        if self.logic.inputSegmentation:
            segmentation = self.logic.inputSegmentation.GetSegmentation()
            self.logic.rightLungMaskSegmentID = segmentation.GetSegmentIdBySegmentName("right lung")
            # print(self.logic.rightLungMaskSegmentID)
            self.logic.leftLungMaskSegmentID = segmentation.GetSegmentIdBySegmentName("left lung")
            # print(self.logic.leftLungMaskSegmentID)

        thresholds = {}
        thresholds['thresholdBullaLower'] = self.ui.BullaRangeWidget.minimumValue
        thresholds['thresholdBullaInflated'] = self.ui.BullaRangeWidget.maximumValue
        thresholds['thresholdInflatedInfiltrated'] = self.ui.InflatedRangeWidget.maximumValue
        thresholds['thresholdInfiltratedCollapsed'] = self.ui.InfiltratedRangeWidget.maximumValue
        thresholds['thresholdCollapsedVessels'] = self.ui.CollapsedRangeWidget.maximumValue
        thresholds['thresholdVesselsUpper'] = self.ui.VesselsRangeWidget.maximumValue
        self.logic.thresholds = thresholds

        settings.setValue("LungCtAnalyzer/BullaRangeWidgetMinimumValue", str(self.ui.BullaRangeWidget.minimumValue))
        settings.setValue("LungCtAnalyzer/BullaRangeWidgetMaximumValue", str(self.ui.BullaRangeWidget.maximumValue))
        settings.setValue("LungCtAnalyzer/InflatedRangeWidgetMinimumValue", str(self.ui.InflatedRangeWidget.minimumValue))
        settings.setValue("LungCtAnalyzer/InflatedRangeWidgetMaximumValue", str(self.ui.InflatedRangeWidget.maximumValue))
        settings.setValue("LungCtAnalyzer/InfiltratedRangeWidgetMinimumValue", str(self.ui.InfiltratedRangeWidget.minimumValue))
        settings.setValue("LungCtAnalyzer/InfiltratedRangeWidgetMaximumValue", str(self.ui.InfiltratedRangeWidget.maximumValue))
        settings.setValue("LungCtAnalyzer/CollapsedRangeWidgetMinimumValue", str(self.ui.CollapsedRangeWidget.minimumValue))
        settings.setValue("LungCtAnalyzer/CollapsedRangeWidgetMaximumValue", str(self.ui.CollapsedRangeWidget.maximumValue))
        settings.setValue("LungCtAnalyzer/VesselsRangeWidgetMinimumValue", str(self.ui.VesselsRangeWidget.minimumValue))
        settings.setValue("LungCtAnalyzer/VesselsRangeWidgetMaximumValue", str(self.ui.VesselsRangeWidget.maximumValue))

        self.batchProcessingTestMode = self.ui.testModeCheckBox.checked
        settings.setValue("LungCtAnalyzer/testModeCheckBoxChecked", str(self.batchProcessingTestMode))          
        self.csvOnly = self.ui.csvOnlyCheckBox.checked
        settings.setValue("LungCtAnalyzer/csvOnlyCheckBoxChecked", str(self.csvOnly))
        
        self.useCalibratedCT = self.ui.useCalibratedCTCheckBox.checked
        settings.setValue("LungCtAnalyzer/useCalibratedCTCheckBoxChecked", str(self.useCalibratedCT))
        
        self.scanInput = self.ui.scanInputCheckBox.checked
        settings.setValue("LungCtAnalyzer/scanInputCheckBoxChecked", str(self.scanInput))

        self.logic.lungMaskedVolume = self.ui.lungMaskedVolumeSelector.currentNode()
        self.logic.outputSegmentation = self.ui.outputSegmentationSelector.currentNode()
        self.logic.resultsTable = self.ui.outputResultsTableSelector.currentNode()
        self.logic.volumeRenderingPropertyNode = self.ui.volumeRenderingPropertyNodeSelector.currentNode()
     
        self.checkForUpdates = self.ui.checkForUpdatesCheckBox.checked
        
        self.logic.generateStatistics = self.ui.generateStatisticsCheckBox.checked
        self.lobeAnalysis = self.ui.lobeAnalysisCheckBox.checked
        settings.setValue("LungCtAnalyzer/lobeAnalysisCheckBoxChecked", str(self.lobeAnalysis))
        self.areaAnalysis = self.ui.areaAnalysisCheckBox.checked
        settings.setValue("LungCtAnalyzer/areaAnalysisCheckBoxChecked", str(self.areaAnalysis))
        self.isNiiGzFormat = self.ui.niigzFormatCheckBox.checked
        settings.setValue("LungCtAnalyzer/niigzFormatCheckBoxChecked", str(self.isNiiGzFormat))
        
        self.logic.countBullae = False

        self._parameterNode.EndModify(wasModified)

    def updateVolumeRenderingProperty(self):
        thresholds = self.logic.thresholds
        volumeRenderingPropertyNode = self.logic.volumeRenderingPropertyNode
        if volumeRenderingPropertyNode:
            scalarOpacity = vtk.vtkPiecewiseFunction()
            colorTransferFunction = vtk.vtkColorTransferFunction()
            scalarOpacity.AddPoint(-3000.0, 0.0)
            colorTransferFunction.AddRGBPoint(-3000.0, 0.0, 0.0, 0.0)
            first = True
            for segmentProperty in self.logic.segmentProperties:
                opacity = self.opacitySliders[segmentProperty["name"]].value * 0.01
                lowerThresholdName, upperThresholdName = segmentProperty["thresholds"]
                lowerThreshold = thresholds[lowerThresholdName]
                upperThreshold = thresholds[upperThresholdName]-0.1
                if first:
                  scalarOpacity.AddPoint(lowerThreshold-0.1, 0.0)
                  first = False
                scalarOpacity.AddPoint(lowerThreshold, opacity)
                scalarOpacity.AddPoint(upperThreshold, opacity)
                color = segmentProperty["color"]
                colorTransferFunction.AddRGBPoint(lowerThreshold, *color)
                colorTransferFunction.AddRGBPoint(upperThreshold, *color)
            scalarOpacity.AddPoint(upperThreshold+0.1, 0.0)
            scalarOpacity.AddPoint(5000, 0.0)
            volumeProperty = volumeRenderingPropertyNode.GetVolumeProperty()
            volumeProperty.GetScalarOpacity().DeepCopy(scalarOpacity)
            volumeProperty.GetRGBTransferFunction().DeepCopy(colorTransferFunction)


    def onInputDirectoryPathLineEditChanged(self):
        self.batchProcessingInputDir = self.ui.inputDirectoryPathLineEdit.currentPath
        settings=qt.QSettings(slicer.app.launcherSettingsFilePath, qt.QSettings.IniFormat)
        settings.setValue("LungCtAnalyzer/batchProcessingInputFolder", self.ui.inputDirectoryPathLineEdit.currentPath);

    def onOutputDirectoryPathLineEditChanged(self):
        self.batchProcessingOutputDir = self.ui.outputDirectoryPathLineEdit.currentPath
        settings=qt.QSettings(slicer.app.launcherSettingsFilePath, qt.QSettings.IniFormat)
        settings.setValue("LungCtAnalyzer/batchProcessingOutputFolder", self.ui.outputDirectoryPathLineEdit.currentPath);

    def showStatusMessage(self, msg, timeoutMsec=500):
        slicer.util.showStatusMessage(msg, timeoutMsec)
        slicer.app.processEvents()

    def onCancelBatchProcessingButton(self):
        print("Batch processing is cancelled by user.")
        self.batchProcessingIsCancelled = True

    def showCriticalError(self, msg):
        slicer.util.messageBox(msg)
        raise ValueError(msg)

    def setThresholdsFromGUI(self):
        scriptThresholds = {
            'thresholdBullaLower': -1050.,
            'thresholdBullaInflated': -950.,
            'thresholdInflatedInfiltrated': -750.,
            'thresholdInfiltratedCollapsed': -400.,
            'thresholdCollapsedVessels': 0.,
            'thresholdVesselsUpper': 3000.,
            }
        scriptThresholds['thresholdBullaLower'] = self.ui.BullaRangeWidget.minimumValue
        scriptThresholds['thresholdBullaInflated'] = self.ui.BullaRangeWidget.maximumValue
        scriptThresholds['thresholdInflatedInfiltrated'] = self.ui.InflatedRangeWidget.maximumValue
        scriptThresholds['thresholdInfiltratedCollapsed'] = self.ui.InfiltratedRangeWidget.maximumValue 
        scriptThresholds['thresholdCollapsedVessels'] = self.ui.CollapsedRangeWidget.maximumValue
        scriptThresholds['thresholdVesselsUpper'] = self.ui.VesselsRangeWidget.maximumValue
        self.logic.setThresholds(self.logic.getParameterNode(), scriptThresholds)


    def onBatchProcessingButton(self):
        self.batchProcessingIsCancelled = False
        if self.batchProcessingInputDir == "":
            self.showCriticalError("No input directory given.")
        if self.batchProcessingOutputDir == "":
            self.showCriticalError("No output directory given.")
        if self.batchProcessingInputDir == self.batchProcessingOutputDir:
            self.showCriticalError("Input and output directotry can not be the same path.")
        if not os.path.exists(self.batchProcessingInputDir):
            self.showCriticalError("Input folder does not exist.")

        counter = 0
        pattern = ''

        pattern = '/' '**/*.mrb'
        
        if self.isNiiGzFormat: 
            pattern = '/' '**/*.nii.gz'
        else:
            pattern = '/' '**/*.mrb'

              
        filesToProcess = 0
        for filepath in glob.iglob(self.batchProcessingInputDir + pattern, recursive=True):
            pathhead, pathtail = os.path.split(filepath)
            if (pathtail.lower() == "ct_seg.mrb" and not self.isNiiGzFormat) or (pathtail.lower() == "ct.nii.gz" and self.isNiiGzFormat):
                # input data must be in subdirectories of self.batchProcessingInputDir
                if pathhead == self.batchProcessingInputDir:
                    self.showCriticalError("Unsupported data structure: Data files in input folder detected, they must be placed in subfolders.")
                # input data must be in immediate child directory of self.batchProcessingInputDir
                parentDir = os.path.dirname(pathhead)
                if parentDir != self.batchProcessingInputDir:
                    self.showCriticalError("Unsupported data structure: There seem to be input data in sub-subfolders of the input folder. Only one subfolder dimension is allowed.")
                filesToProcess += 1
                if self.batchProcessingTestMode: 
                  print("Input file '" + filepath + "' detected ...")
          
        if filesToProcess == 0: 
            self.showCriticalError("No files to process. Each input file must be placed in a separate subdirectory of the input folder.")

        minutesRequired = (filesToProcess * 180) / 60
          
        if not self.batchProcessingTestMode and not slicer.util.confirmYesNoDisplay("If each analysis takes about 3 minutes, batch segmentation of " + str(filesToProcess) + " input files will last around " + str(minutesRequired) + "  minutes. Are you sure you want to continue?"):
            logging.info('Batch processing cancelled by user.')
            return

        if self.batchProcessingTestMode and filesToProcess < 3:
            self.showCriticalError("Not enough input files for test mode (3 needed) during recursive reading below input directory path.")

        startWatchTime = time.time()
        
        self.batchProcessing = True
        counter = 0
        
        if self.scanInput:
            _doanalyze = False
            _dowrite = False
        else: 
            _doanalyze = True
            _dowrite = True
        
        durationProcess = 0
        if self.batchProcessingTestMode:
            filesToProcess = 3
        for filepath in glob.iglob(self.batchProcessingInputDir + pattern, recursive=True):
            pathhead, pathtail = os.path.split(filepath)

            filename = pathtail.lower()
            _doread = False
            if filename == "ct_seg.mrb" and not self.isNiiGzFormat: 
                _doread = True
            if filename == "ct.nii.gz" and self.isNiiGzFormat and not self.useCalibratedCT: 
                _doread = True
            if filename == "ct_calibrated.nii.gz" and self.isNiiGzFormat and self.useCalibratedCT: 
                _doread = True
            if pathhead != self.batchProcessingInputDir: 
                _doread = True
            if _doread:
                startProcessWatchTime = time.time()
                counter += 1
                slicer.mrmlScene.Clear(0)
                if not self.isNiiGzFormat: 
                    # input is not NRRD format 
                    slicer.util.loadScene(filepath)
                    if self.useCalibratedCT: 
                        firstVolumeNode = slicer.util.getFirstNodeByClassByName("vtkMRMLScalarVolumeNode","CT_calibrated")
                        # to prevent crash TODO find out why
                        ctVolumeNode = slicer.util.getFirstNodeByClassByName("vtkMRMLScalarVolumeNode","CT")
                        if ctVolumeNode: 
                            slicer.mrmlScene.RemoveNode(ctVolumeNode)
                    else: 
                        firstVolumeNode = slicer.util.getFirstNodeByClassByName("vtkMRMLScalarVolumeNode","CT")
                    if firstVolumeNode:
                        self.logic.inputVolume = firstVolumeNode
                    else: 
                        raise ValueError("No input volume.")
                    if not self.logic.inputSegmentation:
                        segNode = slicer.util.getFirstNodeByClassByName("vtkMRMLSegmentationNode", "Lung segmentation")
                        if segNode:
                            self.logic.inputSegmentation = segNode
                else:                
                    # input is NIFTI format 
                    # Get color node with random colors
                    randomColorsNode = slicer.mrmlScene.GetNodeByID('vtkMRMLColorTableNodeRandom')
                    rgba = [0, 0, 0, 0]

                    self.inputVolume = slicer.util.loadVolume(filepath)
                    self.logic.inputSegmentation = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode', 'Lung segmentation')
                    pattern = '/' '**/*.nii.gz'
                    print(self.batchProcessingInputDir)
                    # inpathtail is the first level source folder 
                    inpathhead, inpathtail = os.path.split(pathhead)
                    for filepath2 in glob.iglob(self.batchProcessingInputDir + '/' + inpathtail + '/lung_segmentations/' +  pattern, recursive=True):
                        pathhead2, pathtail2 = os.path.split(filepath2)
                        print(f"Importing {filepath2}")
                        underscore_str = pathtail2.replace(".nii.gz","")
                        segmentName = underscore_str.replace("_" , " ")
                        
                        labelmapVolumeNode = slicer.util.loadLabelVolume(filepath2, {"name": segmentName})
                        segmentId = self.logic.inputSegmentation.GetSegmentation().AddEmptySegment(segmentName, segmentName)
                        updatedSegmentIds = vtk.vtkStringArray()
                        updatedSegmentIds.InsertNextValue(segmentId)
                        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, self.logic.inputSegmentation, updatedSegmentIds)
                        slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
                        segmentation = self.logic.inputSegmentation.GetSegmentation()
                        self.logic.rightLungMaskSegmentID = segmentation.GetSegmentIdBySegmentName("right lung")
                        self.logic.leftLungMaskSegmentID = segmentation.GetSegmentIdBySegmentName("left lung")


                print("Analyzing '" + filepath + "' ...", end='\r')
                if _doanalyze: 
                    self.onApplyButton()

                if _dowrite: 
                    outpathhead, outpathtail = os.path.split(pathhead)

                    targetdir = self.batchProcessingOutputDir + "/" + outpathtail + "/"
                    if not os.path.exists(targetdir):
                        os.makedirs(targetdir)
                        
                    self.logic.saveExtendedDataToFile(self.batchProcessingOutputDir + "/results.csv", filepath, counter, outpathtail)
                    self.logic.saveExtendedRegionDataToFile(self.batchProcessingOutputDir + "/regionResults.csv", filepath, counter, outpathtail)
                    self.logic.saveExtendedLobeDataToFile(self.batchProcessingOutputDir + "/lobeResults.csv", filepath, counter, outpathtail)

                    if not self.csvOnly:
                      if self.isNiiGzFormat:
                          # write NIFTI format 
                          self.showStatusMessage("Writing NIFTI output files for input " + str(counter) +  "/" + str(filesToProcess) + " to '" + targetdir + "' ...")
                          for volumeNode in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"):
                            volumeNode.AddDefaultStorageNode()
                            slicer.util.saveNode(volumeNode, targetdir + volumeNode.GetName().lower().replace(" ", "_") + ".nii.gz")
                          numberOfSegments = self.logic.outputSegmentation.GetSegmentation().GetNumberOfSegments()
                          for i in range(numberOfSegments):
                              segment = self.logic.outputSegmentation.GetSegmentation().GetNthSegment(i)
                              labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
                              segID = self.logic.outputSegmentation.GetSegmentation().GetSegmentIdBySegment(segment)
                              strArr = [str(segID)]                      
                              slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode (self.logic.outputSegmentation, strArr, labelmapVolumeNode, self.logic.inputVolume)
                              labelmapVolumeNode.AddDefaultStorageNode()
                              if not os.path.exists(targetdir + "lung_analysis_segmentations/"):
                                  os.makedirs(targetdir + "lung_analysis_segmentations/")
                              slicer.util.saveNode(labelmapVolumeNode, targetdir + "lung_analysis_segmentations/" + segment.GetName().lower().replace(" ", "_") + ".seg.nii.gz")
                              slicer.mrmlScene.RemoveNode(labelmapVolumeNode)  
                      else:
                          # write default format 
                          sceneSaveFilename = targetdir + "ct_seg_analyzed.mrb"
                          self.showStatusMessage("Writing mrb output file for input " + str(counter) +  "/" + str(filesToProcess) + " (last process: {0:.2f} s ".format(durationProcess) + " processing and write time) to '" + sceneSaveFilename + "' ...")
                          if slicer.util.saveScene(sceneSaveFilename):
                              logging.info("Scene saved to: {0}".format(sceneSaveFilename))
                          else:
                              logging.error("Scene saving failed") 
    
                stopProcessWatchTime = time.time()
                durationProcess = stopProcessWatchTime - startProcessWatchTime

                # let slicer process events and update its display
                slicer.app.processEvents()
                time.sleep(3)
          
            if self.batchProcessingIsCancelled: 
                break
            if self.batchProcessingTestMode and counter > 2:
                break
        self.batchProcessing = False             
        stopWatchTime = time.time()
        if self.batchProcessingIsCancelled: 
            print('Batch processing cancelled after {0:.2f} seconds'.format(stopWatchTime-startWatchTime))
            self.showStatusMessage("Batch processing cancelled.")
        else: 
            print('Batch processing completed in {0:.2f} seconds'.format(stopWatchTime-startWatchTime))
            self.showStatusMessage("Batch processing done.")


    def onInputSegmentationSelected(self, segmentationNode):

        if segmentationNode == self.logic.inputSegmentation:
            # no change
            return

        self.updateParameterNodeFromGUI()

    def adjustThresholdSliders(self, lowerSlider, slider, upperSlider):
        wasBlocked = slider.blockSignals(True)
        if lowerSlider:
            wasBlockedLower = lowerSlider.blockSignals(True)
            if slider.minimumValue < lowerSlider.minimumValue:
                slider.minimumValue = lowerSlider.minimumValue
            lowerSlider.maximumValue = slider.minimumValue
            lowerSlider.blockSignals(wasBlockedLower)
        if upperSlider:
            wasBlockedUpper = upperSlider.blockSignals(True)
            if slider.maximumValue > upperSlider.maximumValue:
                slider.maximumValue = upperSlider.maximumValue
            upperSlider.minimumValue = slider.maximumValue
            upperSlider.blockSignals(wasBlockedUpper)
        slider.blockSignals(wasBlocked)
        self.updateParameterNodeFromGUI()
        self.logic.updateMaskedVolumeColors()

    def onBullaRangeWidgetChanged(self):
      self.adjustThresholdSliders(None, self.ui.BullaRangeWidget, self.ui.InflatedRangeWidget)

    def onInflatedRangeWidgetChanged(self):
      self.adjustThresholdSliders(self.ui.BullaRangeWidget, self.ui.InflatedRangeWidget, self.ui.InfiltratedRangeWidget)

    def onInfiltratedRangeWidgetChanged(self):
      self.adjustThresholdSliders(self.ui.InflatedRangeWidget, self.ui.InfiltratedRangeWidget, self.ui.CollapsedRangeWidget)

    def onCollapsedRangeWidgetChanged(self):
      self.adjustThresholdSliders(self.ui.InfiltratedRangeWidget, self.ui.CollapsedRangeWidget, self.ui.VesselsRangeWidget)

    def onVesselsRangeWidgetChanged(self):
      self.adjustThresholdSliders(self.ui.CollapsedRangeWidget, self.ui.VesselsRangeWidget, None)

    def onSaveThresholdsButton(self):
        logging.info('Saving custom thresholds')
        self.logic.saveCustomThresholds()

    def onLoadThresholdsButton(self):
        logging.info('Loading custom thresholds')
        self.logic.loadCustomThresholds()

    def onRestoreDefaultsButton(self):
        logging.info('Restoring default thresholds')
        self.logic.setThresholds(self._parameterNode, self.logic.defaultThresholds)

    def onDownloadCovidData(self):
        if not slicer.util.confirmYesNoDisplay("This will clear all data in the scene. Do you want to continue?", windowTitle=None, parent=None):
            return

        logging.info('Clearing the scene')
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

    def createLightboxImage(self, viewName, destinationFolder, resultImageFilename, reverseOrder=False, rows=6, columns=4):
        sliceWidget = slicer.app.layoutManager().sliceWidget(viewName)
        sliceBounds = [0,0,0,0,0,0]
        sliceWidget.sliceLogic().GetLowestVolumeSliceBounds(sliceBounds)
        if reverseOrder:
            slicePositionRange = [sliceBounds[5], sliceBounds[4]]
        else:
            slicePositionRange = [sliceBounds[4], sliceBounds[5]]

        # Capture slice images, from minimum to maximum position
        # into destinationFolder, with name _lightbox_tmp_image_00001.png, _lightbox_tmp_image_00002.png, ...
        import ScreenCapture
        screenCaptureLogic = ScreenCapture.ScreenCaptureLogic()
        numberOfFrames = rows*columns
        filenamePattern = "_lightbox_tmp_image_%05d.png"
        viewNode = sliceWidget.mrmlSliceNode()
        # Suppress log messages
        def noLog(msg):
            pass
        screenCaptureLogic.addLog=noLog
        # Capture images
        screenCaptureLogic.captureSliceSweep(viewNode, slicePositionRange[0], slicePositionRange[1],
                                             numberOfFrames, destinationFolder, filenamePattern)
        # Create lightbox image
        screenCaptureLogic.createLightboxImage(columns, destinationFolder, filenamePattern, numberOfFrames, resultImageFilename)

        # Clean up
        screenCaptureLogic.deleteTemporaryFiles(destinationFolder, filenamePattern, numberOfFrames)
        

    def openFile(self, filename):
        if sys.platform == "win32":
            filename.replace('/', '\\')
            os.startfile(filename)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, filename])

    def onCreatePDFReportButton(self):

        # Switch to four-up view to have approximately square shaped viewers
        slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)

        printer = qt.QPrinter(qt.QPrinter.PrinterResolution)
        printer.setOutputFormat(qt.QPrinter.PdfFormat)
        printer.setPaperSize(qt.QPrinter.A4)

        familyName = self.logic.resultsTable.GetAttribute("LungCTAnalyzer.patientFamilyName")
        givenName = self.logic.resultsTable.GetAttribute("LungCTAnalyzer.patientGivenName")
        birthDate = self.logic.resultsTable.GetAttribute("LungCTAnalyzer.patientBirthDate")
        examDate = self.logic.resultsTable.GetAttribute("LungCTAnalyzer.examDate")

        from time import gmtime, strftime
        timestampString = strftime("%Y%m%d_%H%M%S", gmtime())
        if familyName and givenName and birthDate and examDate:
            reportPath = f"{self.reportFolder}/{familyName}-{givenName}-{birthDate}-{examDate}-{timestampString}.pdf"
        else:  
            reportPath = f"{self.reportFolder}/LungCT-Report-{timestampString}.pdf"
        printer.setOutputFileName(reportPath)

        userFillString = "................................................."
        if not familyName:
            familyName = userFillString
        if not givenName:
            givenName = userFillString
        if not birthDate:
            birthDate = userFillString
        if not examDate:
            examDate = userFillString

        doc = qt.QTextDocument()
        _html = f"""
        <head>
        <title>Report</title>
        <style>
          td, th {{
            text-align:center; 
          }}
          table {{
            border: 1px solid black;
          }}
        </style>
        </head>  
        <body>
        <h1>Lung CT Analyzer Results</h1>\n
        <br>
        <table>
        <tr>
        <td>Patient last name:</td>
        <td>{familyName}</td>
        </tr>
        <tr>
        <td>Patient first name:</td>
        <td>{givenName}</td>
        </tr>
        <tr>
        <td>Date of birth:</td>
        <td>{birthDate}</td>
        </tr>
        <tr>
        <td>Date of examination:</td>
        <td>{examDate}</td>
        </tr>
        </table>
        <p>The results of the analysis of the CT scan are summarized in the following tables. Segments are created according to their Hounsfield units using predefined threshold ranges. In Table 2 functional versus affected lung volumes are shown. "Emphysema" segment currently includes bronchi and will never be zero. "Infiltration" and "Collapsed" currently include perivascular/-bronchial tissues and will also never be zero. </p>
        <br>
        <h2>Volumetric analysis (Table 1)</h2>
        <br>
        """
        _table=""
        _table+="<table style=""color:black;font-size:10px;"">\n"
        _table+="<tr>\n"
        for col in range(self.logic.resultsTable.GetNumberOfColumns()): 
          _table+="<th>"+self.logic.resultsTable.GetColumnName(col)+"</th>\n"
        _table+="</tr>\n"
        for row in range(self.logic.resultsTable.GetNumberOfRows()): 
            _table+="<tr>\n"
            for col in range(self.logic.resultsTable.GetNumberOfColumns()): 
              if col==0: 
                  _table+="<td style=""text-align:left"">"+self.logic.resultsTable.GetCellText(row,col)+"</td>\n"
              else: 
                  _table+="<td>"+self.logic.resultsTable.GetCellText(row,col)+"</td>\n"
            _table+="</tr>\n"
        _table+="</table>\n"
        _html+=_table
        _html+="""
        <br>
        <h2>Extended analysis (Table 2)</h2>
        <br>
        """
        _table=""
        _table+="<table style=""color:black;font-size:10px;"">\n"
        _table+="<tr>\n"
        for col in range(self.logic.covidResultsTable.GetNumberOfColumns()): 
          _table+="<th>"+self.logic.covidResultsTable.GetColumnName(col)+"</th>\n"
        _table+="</tr>\n"
        for row in range(self.logic.covidResultsTable.GetNumberOfRows()): 
            _table+="<tr>\n"
            for col in range(self.logic.covidResultsTable.GetNumberOfColumns()): 
              if col==0: 
                  _table+="<td style=""text-align:left"">"+self.logic.covidResultsTable.GetCellText(row,col)+"</td>\n"
              else: 
                  _table+="<td>"+self.logic.covidResultsTable.GetCellText(row,col)+"</td>\n"
              
            _table+="</tr>\n"
        _table+="</table>\n"
        _html+=_table

        axialLightboxImageFilename = "_tmp_axial_lightbox.png"
        coronalLightboxImageFilename = "_tmp_coronal_lightbox.png"
        self.createLightboxImage("Red", self.reportFolder, axialLightboxImageFilename, reverseOrder=True)
        self.createLightboxImage("Green", self.reportFolder, coronalLightboxImageFilename)

        _html+="""
        <div id="page2" class="page" style="height: 775px; width: 595px; page-break-before: always;"/>
        <h2>Lightbox (axial view)</h2>
        <br>
        <br>
        """
        _html += f'<img src="{self.reportFolder}/{axialLightboxImageFilename}" width="500" />'

        _html+="""
        <div id="page3" class="page" style="height: 775px; width: 595px; page-break-before: always;"/>
        <h2>Lightbox (coronal view) </h2>
        <br>
        <br>
        """
        _html += f'<img src="{self.reportFolder}/{coronalLightboxImageFilename}" width="500" />'

        _html+="""
        <div id="page4" class="page" style="height: 775px; width: 595px; page-break-before: always;"/>
        <br>
        <h2>Assessment</h2>
        <br>
        <p>................................................................................................</p>
        <p>................................................................................................</p>
        <p>................................................................................................</p>
        <p>................................................................................................</p>
        <p>................................................................................................</p>
        <p>................................................................................................</p>
        <p>................................................................................................</p>
        <p>................................................................................................</p>
        <p>................................................................................................</p>
        <p>................................................................................................</p>
        <br>
        <p>Date  ...................&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Signature   ................................</p>
        <p>""" + self.versionText + """</p>
        </body>
        </html>
        """

        doc.setHtml(_html)
        doc.setPageSize(qt.QSizeF(printer.pageRect().size()))  # hide the page number
        doc.print(printer)

        os.remove(f"{self.reportFolder}/{axialLightboxImageFilename}")
        os.remove(f"{self.reportFolder}/{coronalLightboxImageFilename}")

        # Open in PDF viewer
        logging.info("Starting '"+reportPath+"' ...")
        #slash/backlash replacements because of active directory
        self.openFile(reportPath)
  
    def onApplyButton(self):
        """
        Run processing when user clicks "Apply" button.
        """
        self.checkInputVolumeAndSegmentations()
        
        qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
        try:
            # Compute output
            logging.info('Apply')
            self.logic.lobeAnalysis = self.lobeAnalysis
            self.logic.areaAnalysis = self.areaAnalysis
            self.logic.process()

            self.onShowResultsTable()

            # ensure user sees the new segments
            self.logic.outputSegmentation.GetDisplayNode().Visibility2DOn()

            # hide input segments to make results better visible
            self.logic.inputSegmentation.GetDisplayNode().Visibility2DOff()
            self.logic.inputSegmentation.GetDisplayNode().Visibility3DOff()

            # hide preview in slice view
            slicer.util.setSliceViewerLayers(background=self.logic.inputVolume, foreground=None)
            self.ui.toggleMaskedVolumeDisplay2DPushButton.text = "Show preview in 2D" 


            qt.QApplication.restoreOverrideCursor()
        except Exception as e:
            qt.QApplication.restoreOverrideCursor()
            slicer.util.errorDisplay("Failed to compute results: "+str(e))
            import traceback
            traceback.print_exc()

    def onOpenReportDirectoryButton(self):
        # show file
        logging.info("Open Directory")
        import subprocess        
        subprocess.Popen(f'explorer {os.path.realpath(self.reportFolder)}')
    
    def onReportDirectoryChanged(self):
        
        logging.info("Directory changed")
        self.reportFolder = self.ui.selectReportDirectoryButton.directory
        # save new path locally
        import configparser
        parser = configparser.SafeConfigParser()
        parser.read(slicer.app.slicerUserSettingsFilePath + 'LCTA.INI')
        if parser.has_option('reportFolder', 'path'): 
            parser.set('reportFolder', 'path', self.reportFolder)
        else: 
            parser.add_section('reportFolder')
            parser.set('reportFolder', 'path', self.reportFolder)
        with open(slicer.app.slicerUserSettingsFilePath + 'LCTA.INI', 'w') as configfile:    # save
            parser.write(configfile)

    def onSelectReportDirectoryButton(self):
        logging.info("Directory button clicked")

    def onShowResultsTable(self):
        self.logic.showTable(self.logic.resultsTable)

    def onSaveResultsCSV(self):
        logging.info("Saving CSV ...")
        from time import gmtime, strftime
        timestampString = strftime("%Y%m%d_%H%M%S", gmtime())
        familyName = self.logic.resultsTable.GetAttribute("LungCTAnalyzer.patientFamilyName")
        givenName = self.logic.resultsTable.GetAttribute("LungCTAnalyzer.patientGivenName")
        birthDate = self.logic.resultsTable.GetAttribute("LungCTAnalyzer.patientBirthDate")
        examDate = self.logic.resultsTable.GetAttribute("LungCTAnalyzer.examDate")
        if not self.logic.inputVolume: 
            inputVolumeNodeName = "CT"
        else:
            inputVolumeNodeName = self.logic.inputVolume.GetName()
        
        if familyName and givenName and birthDate and examDate:
            reportPathWithoutExtension = f"{self.reportFolder}/{familyName}-{givenName}-{birthDate}-{examDate}-{timestampString}"
            descriptorString = f"{familyName}-{givenName}-{birthDate}-{examDate}-{timestampString}"
        else:  
            reportPathWithoutExtension = f"{self.reportFolder}/{inputVolumeNodeName}-{timestampString}-LungCTReport"
            descriptorString = f"{timestampString}"
        self.logic.saveDataToFile(reportPathWithoutExtension,descriptorString,"","")

    def onShowCovidResultsTable(self):
        slicer.util.messageBox("COVID segmentations have not been clinically evaluated yet. Do not base treatment decisions on that values.",
            dontShowAgainSettingsKey="LungCTAnalyzer/DontShowCovidResultsWarning",
            icon=qt.QMessageBox.Warning)

        self.logic.showTable(self.logic.covidResultsTable)
        
    def onShowEmphysemaResultsTable(self):
        slicer.util.messageBox("Emphysema segmentations have not been clinically evaluated yet. Do not base treatment decisions on that values.",
            dontShowAgainSettingsKey="LungCTAnalyzer/DontShowCovidResultsWarning",
            icon=qt.QMessageBox.Warning)

        self.logic.showTable(self.logic.emphysemaResultsTable)

    def toggleSegmentationVisibility2D(self, segmentationNode):
        segmentationDisplayNode = segmentationNode.GetDisplayNode()
        if segmentationDisplayNode.GetVisibility2D():
            logging.info('Segments visibility off')
            segmentationDisplayNode.Visibility2DOff()
        else :
            logging.info('Segments visibility on')
            segmentationDisplayNode.Visibility2DOn()

    def toggleSegmentationVisibility3D(self, segmentationNode):
        if segmentationNode.GetDisplayNode().GetVisibility3D() and segmentationNode.GetSegmentation().ContainsRepresentation("Closed surface"):
          segmentationNode.GetDisplayNode().SetVisibility3D(False)
        else:
          segmentationNode.CreateClosedSurfaceRepresentation()
          segmentationNode.GetDisplayNode().SetVisibility3D(True)

    def onToggleInputSegmentationVisibility2D(self):
        self.toggleSegmentationVisibility2D(self.logic.inputSegmentation)
        segmentationDisplayNode = self.logic.inputSegmentation.GetDisplayNode()
        if segmentationDisplayNode.GetVisibility2D():
            self.ui.toggleInputSegmentationVisibility2DPushButton.text = "Hide mask segments in 2D" 
        else: 
            self.ui.toggleInputSegmentationVisibility2DPushButton.text = "Show mask segments in 2D" 

    def onToggleInputSegmentationVisibility3D(self):
        self.toggleSegmentationVisibility3D(self.logic.inputSegmentation)
        if self.logic.inputSegmentation.GetDisplayNode().GetVisibility3D() and self.logic.inputSegmentation.GetSegmentation().ContainsRepresentation("Closed surface"):
            self.ui.toggleInputSegmentationVisibility3DPushButton.text = "Hide mask segments in 3D" 
        else: 
            self.ui.toggleInputSegmentationVisibility3DPushButton.text = "Show mask segments in 3D" 
        
    def onToggleOutputSegmentationVisibility2D(self):
        self.toggleSegmentationVisibility2D(self.logic.outputSegmentation)
        segmentationDisplayNode = self.logic.outputSegmentation.GetDisplayNode()
        if segmentationDisplayNode.GetVisibility2D():
            self.ui.toggleOutputSegmentationVisibility2DPushButton.text = "Hide output segments in 2D" 
        else: 
            self.ui.toggleOutputSegmentationVisibility2DPushButton.text = "Show output segments in 2D" 

    def onToggleOutputSegmentationVisibility3D(self):
        if not self.logic.outputSegmentation.GetSegmentation().ContainsRepresentation("Closed surface"):
            if self.show3DWarning: 
                slicer.util.delayDisplay('Expect up to a minute waiting time until 3D display becomes active.',3000)
                self.show3DWarning = False
        self.toggleSegmentationVisibility3D(self.logic.outputSegmentation)
        if self.logic.outputSegmentation.GetDisplayNode().GetVisibility3D() and self.logic.outputSegmentation.GetSegmentation().ContainsRepresentation("Closed surface"):
            self.ui.toggleOutputSegmentationVisibility3DPushButton.text = "Hide output segments in 3D" 
        else: 
            self.ui.toggleOutputSegmentationVisibility3DPushButton.text = "Show output segments in 3D" 

    def onMaskedVolumeDisplay3D(self):
        self.updateParameterNodeFromGUI()
        if not self.logic.inputVolume or not self.logic.inputSegmentation: 
            slicer.util.messageBox("Input volume or input segmentation missing.")
            raise ValueError("No input volume or segmentation.")
        # Make sure the masked volume is up-to-date
        self.logic.createMaskedVolume()

        volumeRenderingPropertyNode = self.logic.volumeRenderingPropertyNode
        if not volumeRenderingPropertyNode:
            self.logic.volumeRenderingPropertyNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVolumePropertyNode", "LungCT")
            volumeRenderingPropertyNode = self.logic.volumeRenderingPropertyNode
            volumeRenderingPropertyNode.GetVolumeProperty().ShadeOn()
            self.updateVolumeRenderingProperty()


        volRenLogic = slicer.modules.volumerendering.logic()
        volumeNode = self.logic.lungMaskedVolume
        displayNode = volRenLogic.GetFirstVolumeRenderingDisplayNode(volumeNode)
        if displayNode:
            self.logic.wasVisible3D = displayNode.GetVisibility()
            self.ui.toggleMaskedVolumeDisplay3DPushButton.text = "Show preview in 3D"
        else:
            displayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
            self.logic.wasVisible3D = False

        displayNode.SetAndObserveVolumePropertyNodeID(volumeRenderingPropertyNode.GetID())
        displayNode.SetVisibility(not self.logic.wasVisible3D)

        if self.logic.wasVisible3D: 
            self.ui.toggleMaskedVolumeDisplay3DPushButton.text = "Show preview in 3D"
        else:
            self.ui.toggleMaskedVolumeDisplay3DPushButton.text = "Hide preview in 3D"
        
        self.logic.updateMaskedVolumeColors()

        
        if not self.logic.wasVisible3D:
            # center 3D view
            layoutManager = slicer.app.layoutManager()
            if layoutManager.threeDViewCount > 0:
                threeDWidget = layoutManager.threeDWidget(0)
                threeDView = threeDWidget.threeDView()
                threeDView.resetFocalPoint()


    def onMaskedVolumeDisplay2D(self):
        self.updateParameterNodeFromGUI()
        if not self.logic.inputVolume or not self.logic.inputSegmentation: 
            slicer.util.messageBox("Input volume or input segmentation missing.")
            raise ValueError("No input volume or segmentation.")
        self.logic.showLungMaskedVolumeIn2D = not self.logic.showLungMaskedVolumeIn2D

        if self.logic.showLungMaskedVolumeIn2D:
            # Make sure the masked volume is up-to-date
            self.logic.createMaskedVolume()
            self.logic.updateMaskedVolumeColors()
            slicer.util.setSliceViewerLayers(background=self.logic.inputVolume,
                foreground=self.logic.lungMaskedVolume, foregroundOpacity=0.5)
            self.ui.toggleMaskedVolumeDisplay2DPushButton.text = "Hide preview in 2D" 
        else:
          slicer.util.setSliceViewerLayers(background=self.logic.inputVolume, foreground=None)
          self.ui.toggleMaskedVolumeDisplay2DPushButton.text = "Show preview in 2D" 


#
# LungCTAnalyzerLogic
#

class LungCTAnalyzerLogic(ScriptedLoadableModuleLogic):
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
        self.defaultThresholds = {
            'thresholdBullaLower': -1050.,
            'thresholdBullaInflated': -950.,
            'thresholdInflatedInfiltrated': -750.,
            'thresholdInfiltratedCollapsed': -400.,
            'thresholdCollapsedVessels': 0.,
            'thresholdVesselsUpper': 3000.,
            }

        self.segmentProperties = [
            {"name": "Emphysema", "color": [0.0,0.5,0.0], "thresholds": ['thresholdBullaLower', 'thresholdBullaInflated'],"removesmallislands":"no"},
            {"name": "Inflated", "color": [0.0,0.5,1.0], "thresholds": ['thresholdBullaInflated', 'thresholdInflatedInfiltrated'],"removesmallislands":"no"},
            {"name": "Infiltration", "color": [1.0,0.5,0.0], "thresholds": ['thresholdInflatedInfiltrated', 'thresholdInfiltratedCollapsed'],"removesmallislands":"no"},
            {"name": "Collapsed", "color": [1.0,0.0,1.0], "thresholds": ['thresholdInfiltratedCollapsed', 'thresholdCollapsedVessels'],"removesmallislands":"no"},
            {"name": "Vessels", "color": [1.0,0.0,0.0], "thresholds": ['thresholdCollapsedVessels', 'thresholdVesselsUpper'],"removesmallislands":"no"},
            ]

        self.subSegmentProperties = [
            {"name": "ventral", "color": [0.0,0.0,0.0]}, 
            {"name": "dorsal","color": [0.0,0.0,0.0]}, 
            {"name": "upper half","color": [0.0,0.0,0.0]}, 
            {"name": "lower half","color": [0.0,0.0,0.0]}, 
            {"name": "upper","color": [0.0,0.0,0.0]}, 
            {"name": "middle","color": [0.0,0.0,0.0]}, 
            {"name": "lower","color": [0.0,0.0,0.0]}, 
            ]

        self.inputStats = None
        self.outputStats = None
        self.segmentEditorNode = None
        self.segmentEditorWidget = None
        # make progress bar optional for batch operations where not needed
        self.showProgressBar = True
        
    def showStatusMessage(self, msg, timeoutMsec=500):
        slicer.util.showStatusMessage(msg, timeoutMsec)
        slicer.app.processEvents()

    def setThresholds(self, parameterNode, thresholds, overwrite=True):
        wasModified = parameterNode.StartModify()
        for parameterName in thresholds:
            if parameterNode.GetParameter(parameterName) and not overwrite:
                continue
            parameterNode.SetParameter(parameterName, str(thresholds[parameterName]))
        parameterNode.EndModify(wasModified)

    def saveCustomThresholds(self):
        parameterNode = self.getParameterNode()
        thresholds = {}
        
        for parameterName in self.defaultThresholds:
            thresholds[parameterName] = float(parameterNode.GetParameter(parameterName))
        slicer.app.settings().setValue("LungCTAnalyzer/CustomThresholds",str(thresholds))
         
        inputVolume = parameterNode.GetNodeReference("InputVolume")
        if not inputVolume:
            logging.error("Error. Cannot get input volume node, unable to write threshold to volume directory. ")
        else: 
            storageNode = inputVolume.GetStorageNode()
            inputFilename = storageNode.GetFileName()
            inputFilePath = storageNode.GetAbsoluteFilePath(inputFilename)
            head, tail = os.path.split(inputFilePath)
            if not os.path.isdir(head):
                os.mkdir(head)
            with open(head + "/LCTAThresholdDict.txt", "w+") as text_file:
                text_file.write(str(thresholds))
        slicer.util.delayDisplay("Thresholds saved globally and locally.",3000)

    def loadCustomThresholds(self):
        import ast
        
        thresholds = ast.literal_eval(slicer.app.settings().value("LungCTAnalyzer/CustomThresholds", "{}"))
        self.setThresholds(self.getParameterNode(), thresholds)

        parameterNode = self.getParameterNode()
        inputVolume = parameterNode.GetNodeReference("InputVolume")
        if not inputVolume:
            logging.info("Error. Cannot get input volume node reference and unable to write thresholed to the volume directory. ")
        else: 
            storageNode = inputVolume.GetStorageNode()
            inputFilename = storageNode.GetFileName()
            inputFilePath = storageNode.GetAbsoluteFilePath(inputFilename)
            head, tail = os.path.split(inputFilePath)
            file_exists = os.path.isfile(head+"/LCTAThresholdDict.txt")
            if file_exists: 
                with open(head+"/LCTAThresholdDict.txt", "r") as text_file:
                    contents = text_file.read()
                    thresholds = ast.literal_eval(contents)
                    self.setThresholds(self.getParameterNode(), thresholds)
                    slicer.util.delayDisplay("Local thresholds loaded from "+head+"/LCTAThresholdDict.txt",3000)
            else: 
                slicer.util.delayDisplay('No thresholds found.',3000)


    def setDefaultParameters(self, parameterNode):
        """
        Initialize parameter node with default settings.
        """
        self.setThresholds(parameterNode, self.defaultThresholds, overwrite=False)
        if not parameterNode.GetParameter("ComputeImageIntensityStatistics"):
            parameterNode.SetParameter("ComputeImageIntensityStatistics", "true")
            
    def setDefaultThresholds(self, bullaLower,bullaInflated,inflatedInfiltrated,infiltratedCollapsed,collapsedVessels,vesselsUpper):
        """
        Initialize thresholds with special settings.
        """             
        scriptThresholds = {
            'thresholdBullaLower': -1050.,
            'thresholdBullaInflated': -950.,
            'thresholdInflatedInfiltrated': -750.,
            'thresholdInfiltratedCollapsed': -400.,
            'thresholdCollapsedVessels': 0.,
            'thresholdVesselsUpper': 3000.,
            }
        
        scriptThresholds['thresholdBullaLower'] = bullaLower
        scriptThresholds['thresholdBullaInflated'] = bullaInflated
        scriptThresholds['thresholdInflatedInfiltrated'] = inflatedInfiltrated
        scriptThresholds['thresholdInfiltratedCollapsed'] = infiltratedCollapsed
        scriptThresholds['thresholdCollapsedVessels'] = collapsedVessels
        scriptThresholds['thresholdVesselsUpper'] = vesselsUpper
        self.setThresholds(self.getParameterNode(), scriptThresholds)
         

    def updateMaskedVolumeColors(self):
        if not self.lungMaskedVolume:
            return
        #colorNode = slicer.mrmlScene.GetNodeByID(self.lungMaskedVolume.GetDisplayNode().GetColorNodeID())
        colorNode = self.lungMaskedVolume.GetDisplayNode().GetColorNode()
        if colorNode.GetAttribute("Category") != "LungCT":
            colorNode = slicer.vtkMRMLProceduralColorNode()
            colorNode.SetAttribute("Category", "LungCT")
            colorNode.SetType(slicer.vtkMRMLColorTableNode.User)
            colorNode.SetHideFromEditors(False)
            slicer.mrmlScene.AddNode(colorNode)
            self.lungMaskedVolume.GetDisplayNode().SetAndObserveColorNodeID(colorNode.GetID())

        thresholds = self.thresholds

        self.lungMaskedVolume.GetDisplayNode().AutoWindowLevelOff()
        self.lungMaskedVolume.GetDisplayNode().SetWindowLevelMinMax(
            thresholds[self.segmentProperties[0]['thresholds'][0]],
            thresholds[self.segmentProperties[-1]['thresholds'][1]])

        colorTransferFunction = vtk.vtkDiscretizableColorTransferFunction()
        #colorTransferFunction.AddRGBPoint(-3000.0, 0.0, 0.0, 0.0)
        colorTransferFunction.AddRGBPoint(0.0, 0.0, 0.0, 0.0)
        first = True
        offset = -self.lungMaskedVolume.GetDisplayNode().GetWindowLevelMin()
        scale = 255.0/(self.lungMaskedVolume.GetDisplayNode().GetWindowLevelMax()-self.lungMaskedVolume.GetDisplayNode().GetWindowLevelMin())
        for segmentProperty in self.segmentProperties:
            lowerThresholdName, upperThresholdName = segmentProperty["thresholds"]
            lowerThreshold = (thresholds[lowerThresholdName]+offset)*scale
            upperThreshold = (thresholds[upperThresholdName]-0.1+offset)*scale
            if first:
              colorTransferFunction.AddRGBPoint(lowerThreshold-0.1, 0.0, 0.0, 0.0)
              first = False
            color = segmentProperty["color"]
            colorTransferFunction.AddRGBPoint(lowerThreshold, *color)
            colorTransferFunction.AddRGBPoint(upperThreshold, *color)
        colorTransferFunction.AddRGBPoint(upperThreshold+0.1, 0.0, 0.0, 0.0)
        #colorTransferFunction.AddRGBPoint(5000, 0.0, 0.0, 0.0)
        colorTransferFunction.AddRGBPoint(255, 0.0, 0.0, 0.0)
        colorNode.SetAndObserveColorTransferFunction(colorTransferFunction)

    def createResultsTable(self):
        logging.info('Create results table')

        if not self.resultsTable:
            self.resultsTable = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Lung CT analysis results')
        else:
            self.resultsTable.RemoveAllColumns()

        # Compute stats
        self.showStatusMessage('Computing output stats  ...')

        import SegmentStatistics
        
        segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
       
        segStatLogic.getParameterNode().SetParameter("Segmentation", self.outputSegmentation.GetID())
        segStatLogic.getParameterNode().SetParameter("ScalarVolume", self.inputVolume.GetID())
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled", "True" if self.generateStatistics else "False")
        segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.voxel_count.enabled", "False")
        segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.volume_mm3.enabled", "False")
        segStatLogic.computeStatistics()
        segStatLogic.exportToTable(self.resultsTable)
        self.outputStats = segStatLogic.getStatistics()
        # print(str(self.outputStats))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled", "True")

        minThrCol = vtk.vtkFloatArray()
        minThrCol.SetName("MinThr")
        self.resultsTable.AddColumn(minThrCol)
        maxThrCol = vtk.vtkFloatArray()
        maxThrCol.SetName("MaxThr")
        self.resultsTable.AddColumn(maxThrCol)

        parameterNode = self.getParameterNode()

        segmentNameColumn = self.resultsTable.GetTable().GetColumnByName("Segment")
        for side in ['left', 'right']:
            for segmentProperty in self.segmentProperties:
                segmentName = f"{segmentProperty['name']} {side}"
                rowIndex = segmentNameColumn.LookupValue(segmentName)
                lowerThresholdName, upperThresholdName = segmentProperty["thresholds"]
                if rowIndex >=0:
                    minThrCol.SetValue(rowIndex, float(parameterNode.GetParameter(lowerThresholdName)))
                    maxThrCol.SetValue(rowIndex, float(parameterNode.GetParameter(upperThresholdName)))
        self.resultsTable.GetTable().Modified()


        if self.areaAnalysis == True: 
            segmentNameColumn = self.resultsTable.GetTable().GetColumnByName("Segment")
            for side in ['left', 'right']:
                for subSegmentProperty in self.subSegmentProperties:
                    for segmentProperty in self.segmentProperties:
                        segmentName = f"{segmentProperty['name']} {side} {subSegmentProperty['name']}"
                        rowIndex = segmentNameColumn.LookupValue(segmentName)
                        lowerThresholdName, upperThresholdName = segmentProperty["thresholds"]
                        if rowIndex >=0:
                            minThrCol.SetValue(rowIndex, float(parameterNode.GetParameter(lowerThresholdName)))
                            maxThrCol.SetValue(rowIndex, float(parameterNode.GetParameter(upperThresholdName)))
            self.resultsTable.GetTable().Modified()

        # Add patient information as node metadata (available if volume is loaded from DICOM)
        self.resultsTable.SetAttribute("LungCTAnalyzer.patientFamilyName", "")
        self.resultsTable.SetAttribute("LungCTAnalyzer.patientGivenName", "")
        self.resultsTable.SetAttribute("LungCTAnalyzer.patientBirthDate", "")
        self.resultsTable.SetAttribute("LungCTAnalyzer.examDate", "")
        try:
            instUids = self.inputVolume.GetAttribute('DICOM.instanceUIDs').split()
            filePath = slicer.dicomDatabase.fileForInstance(instUids[0])
            import pydicom
            ds = pydicom.read_file(filePath)
            patientName = pydicom.valuerep.PersonName(ds.PatientName)
            self.resultsTable.SetAttribute("LungCTAnalyzer.patientFamilyName", patientName.family_name)
            self.resultsTable.SetAttribute("LungCTAnalyzer.patientGivenName", patientName.given_name)
            self.resultsTable.SetAttribute("LungCTAnalyzer.patientBirthDate", ds.PatientBirthDate)
            self.resultsTable.SetAttribute("LungCTAnalyzer.examDate", ds.StudyDate)
        except:
            pass

    def getVol(self,segId):
        result = 0.
        try:       
            # print(segId)        
            result = float(self.outputStats[segId,"ScalarVolumeSegmentStatisticsPlugin.volume_cm3"])
        except: 
            # not found
            result = 0.
        return result

    def getResultsFor(self, area, explicit = False):

        self.rightResultLungVolume = self.getVol("Emphysema right " + area) + self.getVol("Inflated right " + area) + self.getVol("Infiltration right " + area) + self.getVol("Collapsed right " + area) 
        self.leftResultLungVolume = self.getVol("Emphysema left " + area) + self.getVol("Inflated left " + area) + self.getVol("Infiltration left " + area) + self.getVol("Collapsed left " + area) 
        self.totalResultLungVolume = self.rightResultLungVolume + self.leftResultLungVolume
        if self.totalResultLungVolume > 0.:
            self.rightResultLungVolumePerc = round(self.rightResultLungVolume * 100. / self.totalResultLungVolume)
            self.leftResultLungVolumePerc = round(self.leftResultLungVolume * 100. / self.totalResultLungVolume)
        else:
            self.rightResultLungVolumePerc = -1
            self.leftResultLungVolumePerc = -1
        self.totalResultLungVolumePerc = 100.
        if self.countBullae: 
            self.affectedResultRightVolume = self.getVol("Infiltration right " + area) + self.getVol("Collapsed right " + area) + self.getVol("Emphysema right " + area)
            self.affectedResultLeftVolume = self.getVol("Infiltration left " + area) + self.getVol("Collapsed left " + area) + self.getVol("Emphysema left " + area)
            self.affectedResultTotalVolume = self.affectedResultRightVolume + self.affectedResultLeftVolume
            self.functionalResultRightVolume = self.getVol("Inflated right " + area)
            self.functionalResultLeftVolume = self.getVol("Inflated left " + area)
            self.functionalResultTotalVolume = self.functionalResultRightVolume + self.functionalResultLeftVolume
        else: 
            self.affectedResultRightVolume = self.getVol("Infiltration right " + area) + self.getVol("Collapsed right " + area) 
            self.affectedResultLeftVolume = self.getVol("Infiltration left " + area) + self.getVol("Collapsed left " + area) 
            self.affectedResultTotalVolume = self.affectedResultRightVolume + self.affectedResultLeftVolume
            self.functionalResultRightVolume = self.getVol("Inflated right " + area) + self.getVol("Emphysema right " + area)
            self.functionalResultLeftVolume = self.getVol("Inflated left " + area) + self.getVol("Emphysema right " + area)
            self.functionalResultTotalVolume = self.functionalResultRightVolume + self.functionalResultLeftVolume
        
        self.emphysemaResultRightVolume = self.getVol("Emphysema right " + area)
        self.emphysemaResultLeftVolume = self.getVol("Emphysema left " + area)
        self.emphysemaResultTotalVolume = self.emphysemaResultRightVolume + self.emphysemaResultLeftVolume
        self.infiltratedResultRightVolume = self.getVol("Infiltration right " + area)
        self.infiltratedResultLeftVolume = self.getVol("Infiltration left " + area)
        self.infiltratedResultTotalVolume = self.infiltratedResultRightVolume + self.infiltratedResultLeftVolume
        self.collapsedResultRightVolume = self.getVol("Collapsed right " + area)
        self.collapsedResultLeftVolume = self.getVol("Collapsed left " + area)
        self.collapsedResultTotalVolume = self.collapsedResultRightVolume + self.collapsedResultLeftVolume
        
        if self.totalResultLungVolume > 0.:
            self.functionalResultTotalVolumePerc = round(100 * self.functionalResultTotalVolume / self.totalResultLungVolume)
            self.affectedResultTotalVolumePerc = round(100 * self.affectedResultTotalVolume / self.totalResultLungVolume)
            self.emphysemaResultTotalVolumePerc = round(100 * self.emphysemaResultTotalVolume / self.totalResultLungVolume,1)
            self.infiltratedResultTotalVolumePerc = round(100 * self.infiltratedResultTotalVolume / self.totalResultLungVolume,1)
            self.collapsedResultTotalVolumePerc = round(100 * self.collapsedResultTotalVolume / self.totalResultLungVolume,1)
        else :
            self.functionalResultTotalVolumePerc = -1
            self.affectedResultTotalVolumePerc = -1
            self.emphysemaResultTotalVolumePerc = -1
            self.infiltratedResultTotalVolumePerc = -1
            self.collapsedResultTotalVolumePerc = -1 
        
        if self.rightResultLungVolume > 0.:
            self.functionalResultRightVolumePerc = round(100 * self.functionalResultRightVolume / self.rightResultLungVolume)
            self.affectedResultRightVolumePerc = round(100 * self.affectedResultRightVolume / self.rightResultLungVolume)
            self.emphysemaResultRightVolumePerc = round(100 * self.emphysemaResultRightVolume / self.rightResultLungVolume,1)
            self.infiltratedResultRightVolumePerc = round(100 * self.infiltratedResultRightVolume / self.rightResultLungVolume,1)
            self.collapsedResultRightVolumePerc = round(100 * self.collapsedResultRightVolume / self.rightResultLungVolume,1)
        else :
            self.functionalResultRightVolumePerc = -1
            self.affectedResultRightVolumePerc = -1
            self.emphysemaResultRightVolumePerc = -1
            self.infiltratedResultRightVolumePerc = -1
            self.collapsedResultRightVolumePerc = -1

        if self.leftResultLungVolume > 0.:
            self.functionalResultLeftVolumePerc = round(100 * self.functionalResultLeftVolume / self.leftResultLungVolume)
            self.affectedResultLeftVolumePerc = round(100 * self.affectedResultLeftVolume / self.leftResultLungVolume)
            self.emphysemaResultLeftVolumePerc = round(100 * self.emphysemaResultLeftVolume  / self.leftResultLungVolume,1)
            self.infiltratedResultLeftVolumePerc = round(100 * self.infiltratedResultLeftVolume  / self.leftResultLungVolume,1)
            self.collapsedResultLeftVolumePerc = round(100 * self.collapsedResultLeftVolume  / self.leftResultLungVolume,1)
        else: 
            self.functionalResultLeftVolumePerc = -1
            self.affectedResultLeftVolumePerc = -1
            self.emphysemaResultLeftVolumePerc = -1
            self.infiltratedResultLeftVolumePerc = -1
            self.collapsedResultLeftVolumePerc = -1


    
    def calculateStatistics(self):

        resultsTableNode = self.resultsTable

        col = 1        
        
        self.bulRightLung = self.getVol("Emphysema right")
        self.venRightLung = self.getVol("Inflated right")
        self.infRightLung = self.getVol("Infiltration right")
        self.colRightLung = self.getVol("Collapsed right")
        self.vesRightLung = self.getVol("Vessels right")
        self.bulLeftLung = self.getVol("Emphysema left")
        self.venLeftLung = self.getVol("Inflated left")
        self.infLeftLung = self.getVol("Infiltration left")
        self.colLeftLung = self.getVol("Collapsed left")
        self.vesLeftLung = self.getVol("Vessels left")

        
        self.rightLungVolume = self.getVol("Emphysema right") + self.getVol("Inflated right") + self.getVol("Infiltration right") + self.getVol("Collapsed right")
        self.leftLungVolume = self.getVol("Emphysema left") + self.getVol("Inflated left") + self.getVol("Infiltration left") + self.getVol("Collapsed left") 
        self.totalLungVolume = self.rightLungVolume + self.leftLungVolume

        if self.countBullae: 
            self.functionalRightVolume = self.getVol("Inflated right")
            self.functionalLeftVolume = self.getVol("Inflated left")
            self.functionalTotalVolume = self.venRightLung + self.venLeftLung

            self.affectedRightVolume = self.getVol("Infiltration right") + self.getVol("Collapsed right") + self.getVol("Emphysema right")
            self.affectedLeftVolume = self.getVol("Infiltration left") + self.getVol("Collapsed left") + self.getVol("Emphysema left")
            self.affectedTotalVolume = self.affectedRightVolume + self.affectedLeftVolume
        else: 
            self.functionalRightVolume = self.getVol("Inflated right") + self.getVol("Emphysema right")
            self.functionalLeftVolume = self.getVol("Inflated left") + self.getVol("Emphysema left")
            self.functionalTotalVolume = self.venRightLung + self.venLeftLung

            self.affectedRightVolume = self.getVol("Infiltration right") + self.getVol("Collapsed right") 
            self.affectedLeftVolume = self.getVol("Infiltration left") + self.getVol("Collapsed left") 
            self.affectedTotalVolume = self.affectedRightVolume + self.affectedLeftVolume
        
        self.emphysemaRightVolume = self.getVol("Emphysema right")
        self.emphysemaLeftVolume = self.getVol("Emphysema left")
        self.emphysemaTotalVolume = self.emphysemaRightVolume + self.emphysemaLeftVolume

        self.infiltratedRightVolume = self.getVol("Infiltration right")
        self.infiltratedLeftVolume = self.getVol("Infiltration left")
        self.infiltratedTotalVolume = self.infiltratedRightVolume + self.infiltratedLeftVolume

        self.collapsedRightVolume = self.getVol("Collapsed right")
        self.collapsedLeftVolume = self.getVol("Collapsed left")
        self.collapsedTotalVolume = self.collapsedRightVolume + self.collapsedLeftVolume

        if self.totalLungVolume:
            self.rightLungVolumePerc = round(self.rightLungVolume * 100. / self.totalLungVolume)
            self.leftLungVolumePerc = round(self.leftLungVolume * 100. / self.totalLungVolume)
        else: 
            self.rightLungVolumePerc = self.leftLungVolumePerc = 0
        
        self.totalLungVolumePerc = 100.

        if self.rightLungVolume:
            self.functionalRightVolumePerc = round(100 * self.functionalRightVolume / self.rightLungVolume)
            self.affectedRightVolumePerc = round(100 * self.affectedRightVolume / self.rightLungVolume)
            self.emphysemaRightVolumePerc = round(100 * self.emphysemaRightVolume / self.rightLungVolume,1)
            self.infiltratedRightVolumePerc = round(100 * self.infiltratedRightVolume / self.rightLungVolume,1)
            self.collapsedRightVolumePerc = round(100 * self.collapsedRightVolume / self.rightLungVolume,1)
        else:
            self.functionalRightVolumePerc = self.affectedRightVolumePerc = self.emphysemaRightVolumePerc = self.infiltratedRightVolumePerc = self.collapsedRightVolumePerc = 0
        
        if self.leftLungVolume:
            self.functionalLeftVolumePerc = round(100 * self.functionalLeftVolume / self.leftLungVolume)
            self.affectedLeftVolumePerc = round(100 * self.affectedLeftVolume / self.leftLungVolume)
            self.emphysemaLeftVolumePerc = round(100 * self.emphysemaLeftVolume / self.leftLungVolume,1)
            self.infiltratedLeftVolumePerc = round(100 * self.infiltratedLeftVolume / self.leftLungVolume,1)
            self.collapsedLeftVolumePerc = round(100 * self.collapsedLeftVolume / self.leftLungVolume,1)
        else:
            self.functionalLeftVolumePerc = self.affectedLeftVolumePerc = self.emphysemaLeftVolumePerc = self.infiltratedLeftVolumePerc = self.collapsedLeftVolumePerc = 0
        
        if self.totalLungVolume:
            self.functionalTotalVolumePerc = round(100 * self.functionalTotalVolume / self.totalLungVolume)
            self.affectedTotalVolumePerc = round(100 * self.affectedTotalVolume / self.totalLungVolume)
            self.emphysemaTotalVolumePerc = round(100 * self.emphysemaTotalVolume / self.totalLungVolume,1)
            self.infiltratedTotalVolumePerc = round(100 * self.infiltratedTotalVolume / self.totalLungVolume,1)
            self.collapsedTotalVolumePerc = round(100 * self.collapsedTotalVolume / self.totalLungVolume,1)
        else:
            self.functionalTotalVolumePerc = self.affectedTotalVolumePerc = self.emphysemaTotalVolumePerc = self.infiltratedTotalVolumePerc = self.collapsedTotalVolumePerc = 0


    def createCovidResultsTable(self):
    
        if not self.covidResultsTable:
            self.covidResultsTable = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Lung CT analysis extended results')
        else:
            self.covidResultsTable.RemoveAllColumns()

        labelArray = vtk.vtkStringArray()
        labelArray.SetName("Lung area")

        totalMlArray = vtk.vtkDoubleArray()
        totalMlArray.SetName("Total (ml)")

        functionalMlArray = vtk.vtkDoubleArray()
        functionalMlArray.SetName("Functional (ml)")

        functionalPercentArray = vtk.vtkDoubleArray()
        functionalPercentArray.SetName("Functional (%)")

        affectedMlArray = vtk.vtkDoubleArray()
        affectedMlArray.SetName("Affected (ml)")

        affectedPercentArray = vtk.vtkDoubleArray()
        affectedPercentArray.SetName("Affected (%)")

        emphysemaMlArray = vtk.vtkDoubleArray()
        emphysemaMlArray.SetName("Emphysema (ml)")

        emphysemaPercentArray = vtk.vtkDoubleArray()
        emphysemaPercentArray.SetName("Emphysema (%)")

        infiltratedMlArray = vtk.vtkDoubleArray()
        infiltratedMlArray.SetName("Infiltrated (ml)")

        infiltratedPercentArray = vtk.vtkDoubleArray()
        infiltratedPercentArray.SetName("Infiltrated (%)")

        collapsedMlArray = vtk.vtkDoubleArray()
        collapsedMlArray.SetName("Collapsed (ml)")

        collapsedPercentArray = vtk.vtkDoubleArray()
        collapsedPercentArray.SetName("Collapsed (%)")



        labelArray.InsertNextValue("Total lungs")
        totalMlArray.InsertNextValue(self.totalLungVolume)
        
        functionalMlArray.InsertNextValue(self.functionalTotalVolume)
        functionalPercentArray.InsertNextValue(self.functionalTotalVolumePerc)
        
        affectedMlArray.InsertNextValue(self.affectedTotalVolume)
        affectedPercentArray.InsertNextValue(self.affectedTotalVolumePerc)

        infiltratedMlArray.InsertNextValue(self.infiltratedTotalVolume)
        infiltratedPercentArray.InsertNextValue(self.infiltratedTotalVolumePerc)

        collapsedMlArray.InsertNextValue(self.collapsedTotalVolume)
        collapsedPercentArray.InsertNextValue(self.collapsedTotalVolumePerc)

        emphysemaMlArray.InsertNextValue(self.emphysemaTotalVolume)
        emphysemaPercentArray.InsertNextValue(self.emphysemaTotalVolumePerc)

        labelArray.InsertNextValue("Right lung")
        totalMlArray.InsertNextValue(self.rightLungVolume)
        
        functionalMlArray.InsertNextValue(self.functionalRightVolume)
        functionalPercentArray.InsertNextValue(self.functionalRightVolumePerc)
        
        affectedMlArray.InsertNextValue(self.affectedRightVolume)
        affectedPercentArray.InsertNextValue(self.affectedRightVolumePerc)

        infiltratedMlArray.InsertNextValue(self.infiltratedRightVolume)
        infiltratedPercentArray.InsertNextValue(self.infiltratedRightVolumePerc)

        collapsedMlArray.InsertNextValue(self.collapsedRightVolume)
        collapsedPercentArray.InsertNextValue(self.collapsedRightVolumePerc)

        emphysemaMlArray.InsertNextValue(self.emphysemaRightVolume)
        emphysemaPercentArray.InsertNextValue(self.emphysemaRightVolumePerc)

        labelArray.InsertNextValue("Left lung")
        totalMlArray.InsertNextValue(self.leftLungVolume)
        
        functionalMlArray.InsertNextValue(self.functionalLeftVolume)
        functionalPercentArray.InsertNextValue(self.functionalLeftVolumePerc)
        
        affectedMlArray.InsertNextValue(self.affectedLeftVolume)
        affectedPercentArray.InsertNextValue(self.affectedLeftVolumePerc)

        infiltratedMlArray.InsertNextValue(self.infiltratedLeftVolume)
        infiltratedPercentArray.InsertNextValue(self.infiltratedLeftVolumePerc)

        collapsedMlArray.InsertNextValue(self.collapsedLeftVolume)
        collapsedPercentArray.InsertNextValue(self.collapsedLeftVolumePerc)

        emphysemaMlArray.InsertNextValue(self.emphysemaLeftVolume)
        emphysemaPercentArray.InsertNextValue(self.emphysemaLeftVolumePerc)


        if self.areaAnalysis: 

            for subSegmentProperty in self.subSegmentProperties:
                self.getResultsFor(f"{subSegmentProperty['name']}")
                labelArray.InsertNextValue(f"Lungs {subSegmentProperty['name']}")
                totalMlArray.InsertNextValue(self.totalResultLungVolume)
                functionalMlArray.InsertNextValue(self.functionalResultTotalVolume)
                functionalPercentArray.InsertNextValue(self.functionalResultTotalVolumePerc)
                affectedMlArray.InsertNextValue(self.affectedResultTotalVolume)
                affectedPercentArray.InsertNextValue(self.affectedResultTotalVolumePerc)
                infiltratedMlArray.InsertNextValue(self.infiltratedResultTotalVolume)
                infiltratedPercentArray.InsertNextValue(self.infiltratedResultTotalVolumePerc)
                collapsedMlArray.InsertNextValue(self.collapsedResultTotalVolume)
                collapsedPercentArray.InsertNextValue(self.collapsedResultTotalVolumePerc)
                emphysemaMlArray.InsertNextValue(self.emphysemaResultTotalVolume)
                emphysemaPercentArray.InsertNextValue(self.emphysemaResultTotalVolumePerc)

        if self.lobeAnalysis: 
            for lobeName in ['upper lobe', 'middle lobe', 'lower lobe']:
                    segmentName = lobeName
                    self.getResultsFor(segmentName)
                    labelArray.InsertNextValue("Right " + segmentName)
                    totalMlArray.InsertNextValue(self.rightResultLungVolume)
                    functionalMlArray.InsertNextValue(self.functionalResultRightVolume)
                    functionalPercentArray.InsertNextValue(self.functionalResultRightVolumePerc)
                    affectedMlArray.InsertNextValue(self.affectedResultRightVolume)
                    affectedPercentArray.InsertNextValue(self.affectedResultRightVolumePerc)
                    infiltratedMlArray.InsertNextValue(self.infiltratedResultTotalVolume)
                    infiltratedPercentArray.InsertNextValue(self.infiltratedResultRightVolumePerc)
                    collapsedMlArray.InsertNextValue(self.collapsedResultRightVolume)
                    collapsedPercentArray.InsertNextValue(self.collapsedResultRightVolumePerc)
                    emphysemaMlArray.InsertNextValue(self.emphysemaResultRightVolume)
                    emphysemaPercentArray.InsertNextValue(self.emphysemaResultRightVolumePerc)
            for lobeName in ['upper lobe', 'lower lobe']:
                    segmentName = lobeName
                    self.getResultsFor(segmentName)
                    labelArray.InsertNextValue("Left " + segmentName)
                    totalMlArray.InsertNextValue(self.leftResultLungVolume)
                    functionalMlArray.InsertNextValue(self.functionalResultLeftVolume)
                    functionalPercentArray.InsertNextValue(self.functionalResultLeftVolumePerc)
                    affectedMlArray.InsertNextValue(self.affectedResultLeftVolume)
                    affectedPercentArray.InsertNextValue(self.affectedResultLeftVolumePerc)
                    infiltratedMlArray.InsertNextValue(self.infiltratedResultLeftVolume)
                    infiltratedPercentArray.InsertNextValue(self.infiltratedResultLeftVolumePerc)
                    collapsedMlArray.InsertNextValue(self.collapsedResultLeftVolume)
                    collapsedPercentArray.InsertNextValue(self.collapsedResultLeftVolumePerc)
                    emphysemaMlArray.InsertNextValue(self.emphysemaResultLeftVolume)
                    emphysemaPercentArray.InsertNextValue(self.emphysemaResultLeftVolumePerc)
                        

        self.covidResultsTable.AddColumn(labelArray)
        self.covidResultsTable.AddColumn(totalMlArray)
        self.covidResultsTable.AddColumn(functionalMlArray)
        self.covidResultsTable.AddColumn(functionalPercentArray)
        self.covidResultsTable.AddColumn(emphysemaMlArray)
        self.covidResultsTable.AddColumn(emphysemaPercentArray)
        self.covidResultsTable.AddColumn(infiltratedMlArray)
        self.covidResultsTable.AddColumn(infiltratedPercentArray)
        self.covidResultsTable.AddColumn(collapsedMlArray)
        self.covidResultsTable.AddColumn(collapsedPercentArray)
        self.covidResultsTable.AddColumn(affectedMlArray)
        self.covidResultsTable.AddColumn(affectedPercentArray)

    def createEmphysemaResultsTable(self):
    
        if not self.emphysemaResultsTable:
            self.emphysemaResultsTable = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Lung CT analysis emphysema analysis')
        else:
            self.emphysemaResultsTable.RemoveAllColumns()

        labelArray = vtk.vtkStringArray()
        labelArray.SetName("Lung areas")

        totalMlArray = vtk.vtkDoubleArray()
        totalMlArray.SetName("Total volume (ml)")

        emphysemaMlArray = vtk.vtkDoubleArray()
        emphysemaMlArray.SetName("Emphysema (ml)")

        emphysemaPercentArray = vtk.vtkDoubleArray()
        emphysemaPercentArray.SetName("Emphysema (%)")


        labelArray.InsertNextValue("Total lungs")
        totalMlArray.InsertNextValue(self.totalLungVolume)
                
        emphysemaMlArray.InsertNextValue(self.emphysemaTotalVolume)
        emphysemaPercentArray.InsertNextValue(self.emphysemaTotalVolumePerc)

        labelArray.InsertNextValue("Right lung")
        totalMlArray.InsertNextValue(self.rightLungVolume)
               
        emphysemaMlArray.InsertNextValue(self.emphysemaRightVolume)
        emphysemaPercentArray.InsertNextValue(self.emphysemaRightVolumePerc)

        labelArray.InsertNextValue("Left lung")
        totalMlArray.InsertNextValue(self.leftLungVolume)
                
        emphysemaMlArray.InsertNextValue(self.emphysemaLeftVolume)
        emphysemaPercentArray.InsertNextValue(self.emphysemaLeftVolumePerc)


        if self.areaAnalysis: 
            for subSegmentProperty in self.subSegmentProperties:
                self.getResultsFor(f"{subSegmentProperty['name']}")
                labelArray.InsertNextValue(f"Lungs {subSegmentProperty['name']}")
                totalMlArray.InsertNextValue(self.totalLungVolume)
                emphysemaMlArray.InsertNextValue(self.emphysemaResultTotalVolume)
                emphysemaPercentArray.InsertNextValue(self.emphysemaResultTotalVolumePerc)
                
        if self.lobeAnalysis: 
            segmentName = f"upper lobe"
            self.getResultsFor(segmentName)
            labelArray.InsertNextValue("Right upper lobe")
            totalMlArray.InsertNextValue(self.rightResultLungVolume)
            emphysemaMlArray.InsertNextValue(self.emphysemaResultRightVolume)
            emphysemaPercentArray.InsertNextValue(self.emphysemaResultRightVolumePerc)
            segmentName = f"middle lobe"
            self.getResultsFor(segmentName)
            labelArray.InsertNextValue("Right middle lobe")
            totalMlArray.InsertNextValue(self.rightResultLungVolume)
            emphysemaMlArray.InsertNextValue(self.emphysemaResultRightVolume)
            emphysemaPercentArray.InsertNextValue(self.emphysemaResultRightVolumePerc)
            segmentName = f"lower lobe"
            self.getResultsFor(segmentName)
            labelArray.InsertNextValue("Right lower lobe")
            totalMlArray.InsertNextValue(self.rightResultLungVolume)
            emphysemaMlArray.InsertNextValue(self.emphysemaResultRightVolume)
            emphysemaPercentArray.InsertNextValue(self.emphysemaResultRightVolumePerc)
            segmentName = f"upper lobe"
            self.getResultsFor(segmentName)
            labelArray.InsertNextValue("Left upper lobe")
            totalMlArray.InsertNextValue(self.leftResultLungVolume)
            emphysemaMlArray.InsertNextValue(self.emphysemaResultLeftVolume)
            emphysemaPercentArray.InsertNextValue(self.emphysemaResultLeftVolumePerc)
            segmentName = f"lower lobe"
            self.getResultsFor(segmentName)
            labelArray.InsertNextValue("Left lower lobe")
            totalMlArray.InsertNextValue(self.leftResultLungVolume)
            emphysemaMlArray.InsertNextValue(self.emphysemaResultLeftVolume)
            emphysemaPercentArray.InsertNextValue(self.emphysemaResultLeftVolumePerc)


        self.emphysemaResultsTable.AddColumn(labelArray)
        self.emphysemaResultsTable.AddColumn(totalMlArray)
        self.emphysemaResultsTable.AddColumn(emphysemaMlArray)
        self.emphysemaResultsTable.AddColumn(emphysemaPercentArray)
   
    def saveDataToFile(self, reportPathWithoutExtension,user_str1,user_str2,user_str3):
    
        slicer.util.saveNode(self.resultsTable, reportPathWithoutExtension + "_resultsTable.csv")
        slicer.util.saveNode(self.covidResultsTable, reportPathWithoutExtension + "_extendedResultsTable.csv")
        slicer.util.saveNode(self.emphysemaResultsTable, reportPathWithoutExtension + "_emphysemaResultsTable.csv")

        
        
    def saveExtendedDataToFile(self, filename,user_str1,user_str2,user_str3):

        import os.path


        file_exists = os.path.isfile(filename)

        self.calculateStatistics()

        import csv

        header = [
        'user1',
        'user2',
        'user3',
        'total ml',
        'inflated ml',
        'inflated %',
        'emphysema ml',
        'emphysema %',
        'infiltrated ml',
        'infiltrated %',
        'collapsed ml',
        'collapsed %',
        'affected ml',
        'affected %',
        'right func+aff ml',
        'right inflated ml',
        'right inflated %',
        'right emphysema ml',
        'right emphysema %',
        'right infiltrated ml',
        'right infiltrated %',
        'right collapsed ml',
        'right collapsed %',
        'right affected ml',
        'right affected %',
        'left func+aff ml',
        'left inflated ml',
        'left inflated %',
        'left emphysema ml',
        'left emphysema %',
        'left infiltrated ml',
        'left infiltrated %',
        'left collapsed ml',
        'left collapsed %',
        'left affected ml',
        'left affected %',
        ]

        data = [

        user_str1,
        user_str2,
        user_str3,
        self.totalLungVolume,
        self.functionalTotalVolume,
        self.functionalTotalVolumePerc,
        self.emphysemaTotalVolume,
        self.emphysemaTotalVolumePerc,
        self.infiltratedTotalVolume,
        self.infiltratedTotalVolumePerc,
        self.collapsedTotalVolume,
        self.collapsedTotalVolumePerc,
        self.affectedTotalVolume,
        self.affectedTotalVolumePerc,
        self.rightLungVolume,
        self.functionalRightVolume,
        self.functionalRightVolumePerc,
        self.emphysemaRightVolume,
        self.emphysemaRightVolumePerc,
        self.infiltratedRightVolume,
        self.infiltratedRightVolumePerc,
        self.collapsedRightVolume,
        self.collapsedRightVolumePerc,
        self.affectedRightVolume,
        self.affectedRightVolumePerc,
        self.leftLungVolume,
        self.functionalLeftVolume,
        self.functionalLeftVolumePerc,
        self.emphysemaLeftVolume,
        self.emphysemaLeftVolumePerc,
        self.infiltratedLeftVolume,
        self.infiltratedLeftVolumePerc,
        self.collapsedLeftVolume,
        self.collapsedLeftVolumePerc,
        self.affectedLeftVolume,
        self.affectedLeftVolumePerc,
        ]
        
        
        try:
            with open(filename, 'a') as f:
                if not file_exists:
                    for item in header: 
                        f.write('"')
                        f.write(item)  # file doesn't exist yet, write a header
                        f.write('"')
                        f.write(";")
                    f.write("\n")
                for item in data: 
                    f.write(str(item))  
                    f.write(";")
                f.write("\n")
        except IOError:
            logging.error("I/O error")
        
        
        
    def saveExtendedRegionDataToFile(self, filename,user_str1,user_str2,user_str3):

        import os.path

        file_exists = os.path.isfile(filename)

        self.calculateStatistics()

        import csv

        header = [
        'user1',
        'user2',
        'user3']

        data = [
        user_str1,
        user_str2,
        user_str3]

             
        regions = ["ventral", "dorsal", "upper half", "lower half", "upper", "middle", "lower"]
        areas = [
            'total ml',
            'inflated ml',
            'inflated %',
            'emphysema ml',
            'emphysema %',
            'infiltrated ml',
            'infiltrated %',
            'collapsed ml',
            'collapsed %',
            'affected ml',
            'affected %']
            
        for region in regions: 
            for area in areas: 
                header.append(region + " " + area)

        try:
            with open(filename, 'a') as f:
                if not file_exists:
                    for item in header: 
                        f.write('"')
                        f.write(item)  # file doesn't exist yet, write a header
                        f.write('"')
                        f.write(";")
                    f.write("\n")
                for item in data: 
                    f.write(str(item))  
                    f.write(";")
                if self.areaAnalysis: 
                    for subSegmentProperty in self.subSegmentProperties:
                        self.getResultsFor(f"{subSegmentProperty['name']}")
                        f.write(str(self.totalResultLungVolume))
                        f.write(";")
                        f.write(str(self.functionalResultTotalVolume))
                        f.write(";")
                        f.write(str(self.functionalResultTotalVolumePerc))
                        f.write(";")
                        f.write(str(self.emphysemaResultTotalVolume))
                        f.write(";")
                        f.write(str(self.emphysemaResultTotalVolumePerc))
                        f.write(";")
                        f.write(str(self.infiltratedResultTotalVolume))
                        f.write(";")
                        f.write(str(self.infiltratedResultTotalVolumePerc))
                        f.write(";")
                        f.write(str(self.collapsedResultTotalVolume))
                        f.write(";")
                        f.write(str(self.collapsedResultTotalVolumePerc))
                        f.write(";")
                        f.write(str(self.affectedResultTotalVolume))
                        f.write(";")
                        f.write(str(self.affectedResultTotalVolumePerc))
                        f.write(";")
                f.write("\n")
        except IOError:
            logging.error("I/O error")
        
    def saveExtendedLobeDataToFile(self, filename,user_str1,user_str2,user_str3):

        import os.path

        file_exists = os.path.isfile(filename)

        self.calculateStatistics()

        import csv

        header = [
        'user1',
        'user2',
        'user3']

        data = [
        user_str1,
        user_str2,
        user_str3]

        
        lobes = ["right upper", "right middle", "right lower", "left upper", "left lower"]
        areas = [
            'total ml',
            'inflated ml',
            'inflated %',
            'emphysema ml',
            'emphysema %',
            'infiltrated ml',
            'infiltrated %',
            'collapsed ml',
            'collapsed %',
            'affected ml',
            'affected %']
            
        for lobe in lobes: 
            for area in areas: 
                header.append(lobe + " " + area)


        try:
            with open(filename, 'a') as f:
                if not file_exists:
                    for item in header: 
                        f.write('"')
                        f.write(item)  # file doesn't exist yet, write a header
                        f.write('"')
                        f.write(";")
                    f.write("\n")
                for item in data: 
                    f.write(str(item))  
                    f.write(";")
                if self.lobeAnalysis: 
                    lobenames = ["upper lobe", "middle lobe", "lower lobe"]
                    for lobename in lobenames:
                        self.getResultsFor(lobename)
                        f.write(str(self.rightResultLungVolume))
                        f.write(";")
                        f.write(str(self.functionalResultRightVolume))
                        f.write(";")
                        f.write(str(self.functionalResultRightVolumePerc))
                        f.write(";")
                        f.write(str(self.emphysemaResultRightVolume))
                        f.write(";")
                        f.write(str(self.emphysemaResultRightVolumePerc))
                        f.write(";")
                        f.write(str(self.infiltratedResultRightVolume))
                        f.write(";")
                        f.write(str(self.infiltratedResultRightVolumePerc))
                        f.write(";")
                        f.write(str(self.collapsedResultRightVolume))
                        f.write(";")
                        f.write(str(self.collapsedResultRightVolumePerc))
                        f.write(";")
                        f.write(str(self.affectedResultRightVolume))
                        f.write(";")
                        f.write(str(self.affectedResultRightVolumePerc))
                        f.write(";")
                    lobenames = ["upper lobe", "lower lobe"]
                    for lobename in lobenames:
                        self.getResultsFor(lobename)
                        f.write(str(self.leftResultLungVolume))
                        f.write(";")
                        f.write(str(self.functionalResultLeftVolume))
                        f.write(";")
                        f.write(str(self.functionalResultLeftVolumePerc))
                        f.write(";")
                        f.write(str(self.emphysemaResultLeftVolume))
                        f.write(";")
                        f.write(str(self.emphysemaResultLeftVolumePerc))
                        f.write(";")
                        f.write(str(self.infiltratedResultLeftVolume))
                        f.write(";")
                        f.write(str(self.infiltratedResultLeftVolumePerc))
                        f.write(";")
                        f.write(str(self.collapsedResultLeftVolume))
                        f.write(";")
                        f.write(str(self.collapsedResultLeftVolumePerc))
                        f.write(";")
                        f.write(str(self.affectedResultLeftVolume))
                        f.write(";")
                        f.write(str(self.affectedResultLeftVolumePerc))
                        f.write(";")
                f.write("\n")
        except IOError:
            logging.error("I/O error")
        

    @property
    def inputVolume(self):
        return self.getParameterNode().GetNodeReference("InputVolume")

    @inputVolume.setter
    def inputVolume(self, node):
        self.getParameterNode().SetNodeReferenceID("InputVolume", node.GetID() if node else None)

    @property
    def inputSegmentation(self):
        return self.getParameterNode().GetNodeReference("InputSegmentation")

    @inputSegmentation.setter
    def inputSegmentation(self, node):
        self.getParameterNode().SetNodeReferenceID("InputSegmentation", node.GetID() if node else None)

    @property
    def resultsTable(self):
        return self.getParameterNode().GetNodeReference("ResultsTable")

    @resultsTable.setter
    def resultsTable(self, node):
        self.getParameterNode().SetNodeReferenceID("ResultsTable", node.GetID() if node else None)

    @property
    def covidResultsTable(self):
        return self.getParameterNode().GetNodeReference("CovidResultsTable")

    @covidResultsTable.setter
    def covidResultsTable(self, node):
        self.getParameterNode().SetNodeReferenceID("CovidResultsTable", node.GetID() if node else None)

    @property
    def emphysemaResultsTable(self):
        return self.getParameterNode().GetNodeReference("EmphysemaResultsTable")

    @emphysemaResultsTable.setter
    def emphysemaResultsTable(self, node):
        self.getParameterNode().SetNodeReferenceID("EmphysemaResultsTable", node.GetID() if node else None)

    @property
    def volumeRenderingPropertyNode(self):
        return self.getParameterNode().GetNodeReference("VolumeRenderingPropertyNode")

    @volumeRenderingPropertyNode.setter
    def volumeRenderingPropertyNode(self, node):
        self.getParameterNode().SetNodeReferenceID("VolumeRenderingPropertyNode", node.GetID() if node else None)


    @property
    def rightLungMaskSegmentID(self):
      return self.getParameterNode().GetParameter("RightLungMaskSegmentID")

    @rightLungMaskSegmentID.setter
    def rightLungMaskSegmentID(self, value):
        self.getParameterNode().SetParameter("RightLungMaskSegmentID", value)
    
    @property
    def leftLungMaskSegmentID(self):
      return self.getParameterNode().GetParameter("LeftLungMaskSegmentID")

    @leftLungMaskSegmentID.setter
    def leftLungMaskSegmentID(self, value):
        self.getParameterNode().SetParameter("LeftLungMaskSegmentID", value)

    @property
    def generateStatistics(self):
      return self.getParameterNode().GetParameter("GenerateStatistics") == "true"

    @generateStatistics.setter
    def generateStatistics(self, on):
        self.getParameterNode().SetParameter("GenerateStatistics", "true" if on else "false")

    @property
    def lobeAnalysis(self):
      return self.getParameterNode().GetParameter("LobeAnalysis") == "true"

    @lobeAnalysis.setter
    def lobeAnalysis(self, on):
        self.getParameterNode().SetParameter("LobeAnalysis", "true" if on else "false")

    @property
    def areaAnalysis(self):
      return self.getParameterNode().GetParameter("AreaAnalysis") == "true"

    @areaAnalysis.setter
    def areaAnalysis(self, on):
        self.getParameterNode().SetParameter("AreaAnalysis", "true" if on else "false")

    @property
    def countBullae(self):
      return self.getParameterNode().GetParameter("CountBullae") == "true"

    @countBullae.setter
    def countBullae(self, on):
        self.getParameterNode().SetParameter("CountBullae", "true" if on else "false")

    @property
    def lungMaskedVolume(self):
        return self.getParameterNode().GetNodeReference("LungMaskedVolume")

    @lungMaskedVolume.setter
    def lungMaskedVolume(self, node):
        self.getParameterNode().SetNodeReferenceID("LungMaskedVolume", node.GetID() if node else None)

    @property
    def showLungMaskedVolumeIn2D(self):
        return self.getParameterNode().GetParameter("ShowLungMaskedVolumeIn2D") == "true"

    @showLungMaskedVolumeIn2D.setter
    def showLungMaskedVolumeIn2D(self, on):
        self.getParameterNode().SetParameter("ShowLungMaskedVolumeIn2D", "true" if on else "false")

    @property
    def outputSegmentation(self):
        return self.getParameterNode().GetNodeReference("OutputSegmentation")

    @outputSegmentation.setter
    def outputSegmentation(self, node):
        self.getParameterNode().SetNodeReferenceID("OutputSegmentation", node.GetID() if node else None)

    @property
    def thresholds(self):
        parameterNode = self.getParameterNode()
        values = {}
        for parameterName in self.defaultThresholds:
            values[parameterName] = float(parameterNode.GetParameter(parameterName))
        return values
        

    @thresholds.setter
    def thresholds(self, values):
        parameterNode = self.getParameterNode()
        wasModified = parameterNode.StartModify()
        for parameterName in values:
            parameterNode.SetParameter(parameterName, str(values[parameterName]))
        parameterNode.EndModify(wasModified)

    def trimSegmentWithCube(self, id,r,a,s,offs_r,offs_a,offs_s) :
        

        self.segmentEditorNode.SetSelectedSegmentID(id)
        if not self.segmentEditorWidget.effectByName("Surface cut"):
            slicer.util.errorDisplay("Please install 'SegmentEditorExtraEffects' extension using Extension Manager.")
            raise ValueError("Installation of 'SegmentEditorExtraEffects' extension required.")

        self.segmentEditorWidget.setActiveEffectByName("Surface cut")

        effect = self.segmentEditorWidget.activeEffect()

        effect.self().fiducialPlacementToggle.placeButton().click()
        
        _sv = 50
        
        if "dorsal" in id: 
            right_safety = _sv
            left_safety = _sv
            anterior_safety = _sv
            posterior_safety = 0
            superior_safety = _sv
            inferior_safety = _sv
        if "ventral" in id: 
            right_safety = _sv
            left_safety = _sv
            anterior_safety = 0
            posterior_safety = _sv
            superior_safety = _sv
            inferior_safety = _sv
        if "upper" in id: 
            right_safety = _sv
            left_safety = _sv
            anterior_safety = _sv
            posterior_safety = _sv
            superior_safety = 0
            inferior_safety = _sv
        if "middle" in id: 
            right_safety = _sv
            left_safety = _sv
            anterior_safety = _sv
            posterior_safety = _sv
            superior_safety = 0
            inferior_safety = 0
        if "lower" in id: 
            right_safety = _sv
            left_safety = _sv
            anterior_safety = _sv
            posterior_safety = _sv
            superior_safety = _sv
            inferior_safety = 0
            
        # trim with cube

        points =[[r-offs_r-left_safety, a+offs_a+anterior_safety, s+offs_s+superior_safety], [r+offs_r+right_safety, a+offs_a+anterior_safety, s+offs_s+superior_safety],
                 [r+offs_r+right_safety, a+offs_a+anterior_safety, s-offs_s-inferior_safety], [r-offs_r-left_safety, a+offs_a+anterior_safety, s-offs_s-inferior_safety],
                 [r-offs_r-left_safety, a-offs_a-posterior_safety, s+offs_s+superior_safety], [r+offs_r+right_safety, a-offs_a-posterior_safety, s+offs_s+superior_safety],
                 [r+offs_r+right_safety, a-offs_a-posterior_safety, s-offs_s-inferior_safety], [r-offs_r-left_safety, a-offs_a-posterior_safety, s-offs_s-inferior_safety],
                ]

        for p in points:
            effect.self().segmentMarkupNode.AddFiducialFromArray(p)
        
        effect.setParameter("Operation","ERASE_INSIDE")
        effect.setParameter("SmoothModel","0")

        effect.self().onApply()
        


    def cropSubSegmentation(self, segmentSrc, sideId, typeStr): 


        inputStats = self.inputStats
        segmentId = sideId + " lung"
        centroid_ras = inputStats[segmentId,"LabelmapSegmentStatisticsPlugin.centroid_ras"]
        # get bounding box
        import numpy as np
        obb_origin_ras = np.array(inputStats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_origin_ras"])
        obb_diameter_mm = np.array(inputStats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_diameter_mm"])
        obb_direction_ras_x = np.array(inputStats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_x"])
        obb_direction_ras_y = np.array(inputStats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_y"])
        obb_direction_ras_z = np.array(inputStats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_z"])
        obb_center_ras = obb_origin_ras+0.5*(obb_diameter_mm[0] * obb_direction_ras_x + obb_diameter_mm[1] * obb_direction_ras_y + obb_diameter_mm[2] * obb_direction_ras_z)
        
        axialLungDiameter = obb_diameter_mm[0]
        sagittalLungDiameter = obb_diameter_mm[1]
        coronalLungDiameter = obb_diameter_mm[2]
        coronalApex = centroid_ras[2] + (coronalLungDiameter/2.)
        if typeStr == "ventral": 
            ####### ventral
                        
            r = centroid_ras[0]
            a = centroid_ras[1] - (sagittalLungDiameter/4.)
            s = centroid_ras[2]
            
            
            crop_r = (axialLungDiameter/2.)  
            crop_a = (sagittalLungDiameter/4.)
            crop_s = (coronalLungDiameter/2.)

            
            self.showStatusMessage(' Cropping ' + segmentSrc.GetName() +  ' segment ...')
            self.trimSegmentWithCube(segmentSrc.GetName(),r,a,s,crop_r,crop_a,crop_s)

        elif  typeStr == "dorsal": 
            ####### dorsal
            
            r = centroid_ras[0]
            a = centroid_ras[1] + (sagittalLungDiameter/4.)
            s = centroid_ras[2]
            
            crop_r = (axialLungDiameter/2.)  
            crop_a = (sagittalLungDiameter/4.)
            crop_s = (coronalLungDiameter/2.)

            self.showStatusMessage(' Cropping ' + segmentSrc.GetName() +  ' segment ...')
            self.trimSegmentWithCube(segmentSrc.GetName(),r,a,s,crop_r,crop_a,crop_s)

        elif  typeStr == "upper half": 
            ####### upper half
            
            r = centroid_ras[0]
            a = centroid_ras[1] 
            s = centroid_ras[2] - (coronalLungDiameter/2.)
            
            crop_r = axialLungDiameter
            crop_a = sagittalLungDiameter
            crop_s = coronalLungDiameter/2.

            self.showStatusMessage(' Cropping ' + segmentSrc.GetName() +  ' segment ...')
            self.trimSegmentWithCube(segmentSrc.GetName(),r,a,s,crop_r,crop_a,crop_s)

        elif  typeStr == "lower half": 
            ####### lower half
            
            r = centroid_ras[0]
            a = centroid_ras[1] 
            s = centroid_ras[2] + (coronalLungDiameter/2.)
            
            crop_r = axialLungDiameter
            crop_a = sagittalLungDiameter
            crop_s = coronalLungDiameter/2.

            self.showStatusMessage(' Cropping ' + segmentSrc.GetName() +  ' segment ...')
            self.trimSegmentWithCube(segmentSrc.GetName(),r,a,s,crop_r,crop_a,crop_s)

        elif typeStr == "upper": 
            ####### upper
            
            r = centroid_ras[0]
            a = centroid_ras[1] 
            s = coronalApex - ((coronalLungDiameter/3.)*2.)
            
            crop_r = (axialLungDiameter/2.)
            crop_a = (sagittalLungDiameter/2.)
            crop_s = (coronalLungDiameter/3.)

            self.showStatusMessage(' Cropping ' + segmentSrc.GetName() +  ' segment ...')
            self.trimSegmentWithCube(segmentSrc.GetName(),r,a,s,crop_r,crop_a,crop_s)
   
        elif typeStr == "middle": 
            ####### middle
            
            ####### crop upper part
            r = centroid_ras[0]
            a = centroid_ras[1] 
            s = coronalApex

            
            crop_r = (axialLungDiameter/2.) 
            crop_a = (sagittalLungDiameter/2.)
            crop_s = (coronalLungDiameter/3.)

            self.showStatusMessage(' Cropping ' + segmentSrc.GetName() +  ' segment ...')
            self.trimSegmentWithCube(segmentSrc.GetName(),r,a,s,crop_r,crop_a,crop_s)

            ####### crop lower part
            r = centroid_ras[0]
            a = centroid_ras[1] 
            s = coronalApex - coronalLungDiameter 

            crop_r = (axialLungDiameter/2.)  
            crop_a = (sagittalLungDiameter/2.)
            crop_s = (coronalLungDiameter/3.)

            self.trimSegmentWithCube(segmentSrc.GetName(),r,a,s,crop_r,crop_a,crop_s)

        elif typeStr == "lower": 
            ####### lower
            
            r = centroid_ras[0]
            a = centroid_ras[1] 
            s = coronalApex - (coronalLungDiameter/3.)

            
            crop_r = (axialLungDiameter/2.)  
            crop_a = (sagittalLungDiameter/2.)
            crop_s = (coronalLungDiameter/3.)

            self.showStatusMessage(' Cropping ' + segmentSrc.GetName() +  ' segment ...')
            self.trimSegmentWithCube(segmentSrc.GetName(),r,a,s,crop_r,crop_a,crop_s)


    def showProgress(self,progressText):
        if self.showProgressBar:
            # Update progress value
            self.progressbar.setValue(self.progress)
            self.progress += self.progressStep
            # Update label text
            self.progressbar.labelText = progressText
        slicer.app.processEvents()
        self.showStatusMessage(progressText)

    def subtractSegmentFromSegment(self, segmentationNode, modifierSegmentName, selectedSegmentName):
        self.showStatusMessage('Subtracting ' + modifierSegmentName + ' from ' + selectedSegmentName + ' ...')
        modifierSegmentID = segmentationNode.GetSegmentation().GetSegmentIdBySegmentName(modifierSegmentName)
        selectedSegmentID = segmentationNode.GetSegmentation().GetSegmentIdBySegmentName(selectedSegmentName)

        self.segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
        self.segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
        self.segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        self.segmentEditorWidget.setMRMLSegmentEditorNode(self.segmentEditorNode)
        self.segmentEditorWidget.setSegmentationNode(self.inputSegmentation)
        self.segmentEditorWidget.setSourceVolumeNode(self.maskLabelVolume)

        self.segmentEditorWidget.setSegmentationNode(segmentationNode)
        self.segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone) 
        self.segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)
        self.segmentEditorNode.SetSelectedSegmentID(selectedSegmentID)
        self.segmentEditorWidget.setActiveEffectByName("Logical operators")
        effect = self.segmentEditorWidget.activeEffect()
        effect.setParameter("BypassMasking","1")
        effect.setParameter("ModifierSegmentID",modifierSegmentID)
        effect.setParameter("Operation","SUBTRACT")
        effect.self().onApply()

        # Delete temporary segment editor
        logging.info('Deleting temporary segment editor ... ')
        self.segmentEditorWidget = None
        slicer.mrmlScene.RemoveNode(self.segmentEditorNode)    
        self.segmentEditorNode = None

    def increment_counter(self, counter):
        try:
            url = 'http://scientific-networks.de/increment_counter.php'
            api_key = "WVnB2F7Uibt2TC"
            params = {'api_key': api_key, 'counter': counter}
            requests.get(url, params=params,  timeout=5)
        except requests.exceptions.RequestException as e:
            print(f"Unable to increment counter: {e}")
            


    def increment_users(self,program):
        try:
            url = 'http://scientific-networks.de/increment_users.php'
            api_key = "WVnB2F7Uibt2TC"
            params = {'api_key': api_key, 'program': program}
            requests.get(url, params=params,  timeout=5)
        except requests.exceptions.RequestException as e:
            print(f"Unable to increment counter: {e}")
    
    def process(self):
        """
        Run the processing algorithm.
        Can be used without GUI widget.
        """
        self.increment_counter('counter_lcta')  # increment counter_lcta
        self.increment_users('lcta')  # increment usage lcta

        logging.info('Processing started.')
        import time
        startTime = time.time()
        if self.showProgressBar:
            # Prevent progress dialog from automatically closing
            self.progressbar = slicer.util.createProgressDialog(parent=slicer.util.mainWindow(), windowTitle='Processing...', autoClose=False)
            self.progressbar.setCancelButton(None)

        self.progress =0
        steps = 7
        if self.areaAnalysis: 
            steps +=1
            
        self.progressStep = 100/steps
        self.showProgress("Starting processing ...")

        # Validate inputs

        parameterNode = self.getParameterNode()

        inputVolume = parameterNode.GetNodeReference("InputVolume")
        if not inputVolume:
            self.progressbar.close()
            raise ValueError("Input lung CT is invalid.")


        inputSegmentationNode = parameterNode.GetNodeReference("InputSegmentation")
        if not inputSegmentationNode:
            self.progressbar.close()
            raise ValueError("Input lung segmentation node is invalid.")

        rightMaskSegmentName = inputSegmentationNode.GetSegmentation().GetSegment(self.rightLungMaskSegmentID).GetName().upper()
        leftMaskSegmentName = inputSegmentationNode.GetSegmentation().GetSegment(self.leftLungMaskSegmentID).GetName().upper()
        if ( (rightMaskSegmentName != "RIGHT LUNG" and rightMaskSegmentName != "RIGHT LUNG MASK") or
            (leftMaskSegmentName != "LEFT LUNG" and leftMaskSegmentName != "LEFT LUNG MASK") ):
            if not slicer.util.confirmYesNoDisplay("Warning: segment names are expected to be 'left/right lung' ('left/right lung mask'). Are you sure you want to continue?"):
              raise UserWarning("User cancelled the analysis.")

        if ( (rightMaskSegmentName == "RIGHT LUNG MASK") or (leftMaskSegmentName == "LEFT LUNG MASK") ):
            #inputSegmentationNode.GetSegmentation().GetSegment(self.rightLungMaskSegmentID).SetName("right lung")
            #inputSegmentationNode.GetSegmentation().GetSegment(self.leftLungMaskSegmentID).SetName("left lung")
            segmentationNode.GetSegmentation().GetNthSegment(0).SetName("right lung")
            inputSegmentationNode.GetSegmentation().GetNthSegment(1).SetName("left lung")
            # for compatibitlity reasons - regional lung area definition needs to have these names

 
        self.showProgress("Creating masked volume ...")

        # create masked volume
        self.maskLabelVolume = self.createMaskedVolume(keepMaskLabelVolume=True)


        # Compute centroids

        import SegmentStatistics
        self.showProgress("Computing input stats and centroids ...")
        logging.info("Computing input stats and centroids ...")    
        rightMaskSegmentName = inputSegmentationNode.GetSegmentation().GetSegment(self.rightLungMaskSegmentID).GetName()        
        leftMaskSegmentName = inputSegmentationNode.GetSegmentation().GetSegment(self.leftLungMaskSegmentID).GetName()        
        
        inputSegmentationNode.GetDisplayNode().SetSegmentVisibility(rightMaskSegmentName,True)
        inputSegmentationNode.GetDisplayNode().SetSegmentVisibility(leftMaskSegmentName,True)
        segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
                
        segStatLogic.getParameterNode().SetParameter("Segmentation", inputSegmentationNode.GetID())

        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled", "True")
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.centroid_ras.enabled", str(True))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_origin_ras.enabled",str(True))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_diameter_mm.enabled",str(True))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_x.enabled",str(True))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_y.enabled",str(True))
        segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_z.enabled",str(True))
        segStatLogic.computeStatistics()
        inputStats = segStatLogic.getStatistics()
        self.inputStats = inputStats
        #print("Input stats: "+ str(self.inputStats))
        


        # create main outout segmentation
        # Update progress value
        self.showProgress("Creating thresholded segments ...")
        self.createThresholdedSegments(self.maskLabelVolume)


        self.segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
        self.segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
        self.segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        self.segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)
        self.segmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteAllSegments)
        self.segmentEditorWidget.setMRMLSegmentEditorNode(self.segmentEditorNode)
        self.segmentEditorWidget.setSegmentationNode(self.outputSegmentation)
        self.segmentEditorWidget.setSourceVolumeNode(self.maskLabelVolume)

        #for side in ['right','left']:
            # fill holes in vessel segmentations
            #self.showProgress(f'Filling holes in segment "Vessels {side}" ...')
            #self.segmentEditorNode.SetSelectedSegmentID(f'Vessels {side}')
            #self.segmentEditorWidget.setActiveEffectByName("Smoothing")
            #effect = self.segmentEditorWidget.activeEffect()
            #effect.setParameter("SmoothingMethod","MORPHOLOGICAL_CLOSING")
            #spacing = self.inputVolume.GetSpacing()
            #kernelSize = spacing[0] * 3.
            #effect.setParameter("KernelSizeMm",str(kernelSize))
            #effect.self().onApply()

        # Delete temporary segment editor
        logging.info('Deleting temporary segment editor ... ')
        self.segmentEditorWidget = None
        slicer.mrmlScene.RemoveNode(self.segmentEditorNode)    
        self.segmentEditorNode = None      
        
        if self.areaAnalysis == True: 

            # split lung into subregions
            self.showProgress("Splitting output segments into subregions ...")
   
            logging.info('Creating temporary segment editor ... ')
            self.segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
            self.segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
            self.segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
            self.segmentEditorWidget.setMRMLSegmentEditorNode(self.segmentEditorNode)
            self.segmentEditorWidget.setSegmentationNode(self.outputSegmentation)
            self.segmentEditorWidget.setSourceVolumeNode(self.maskLabelVolume)

            for side in ['left', 'right']:
                for region in ['ventral', 'dorsal', 'upper half', 'lower half', 'upper', 'middle', 'lower']: 
                    for segmentProperty in self.segmentProperties:
                        segmentName = f"{segmentProperty['name']} {side}"
                        sourceSegID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
                        sourceSeg = self.outputSegmentation.GetSegmentation().GetSegment(sourceSegID)
                        newSegId = self.outputSegmentation.GetSegmentation().AddEmptySegment(segmentName + " " + region,segmentName +" " + region,segmentProperty['color'])
                        newSeg = self.outputSegmentation.GetSegmentation().GetSegment(newSegId)
                        newSeg.DeepCopy(sourceSeg)
                        newSeg.SetName(segmentName + " " + region)
                        self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(newSeg.GetName(),True)
                        self.cropSubSegmentation(newSeg, side, region)
                    
             # Delete temporary segment editor
            logging.info('Deleting temporary segment editor ... ')
            self.segmentEditorWidget = None
            slicer.mrmlScene.RemoveNode(self.segmentEditorNode)    
            self.segmentEditorNode = None

        if self.lobeAnalysis == True:
        
            # copy lobe masks from input to output segmentation
            self.showProgress("Copying lobe masks ...")
            numberLobesFound = 0
            for lobeName in ['right upper lobe', 'right middle lobe', 'right lower lobe', 'left upper lobe', 'left lower lobe' ]:
                sourceSegID = self.inputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(lobeName)
                sourceSeg = self.inputSegmentation.GetSegmentation().GetSegment(sourceSegID)
                if sourceSeg:
                    numberLobesFound += 1
                newSegId = self.outputSegmentation.GetSegmentation().AddEmptySegment(lobeName, lobeName)
                newSeg = self.outputSegmentation.GetSegmentation().GetSegment(newSegId)
                newSeg.DeepCopy(sourceSeg)
            
            lobeName = "upper lobe"
            side = "right"
            self.showProgress("Analyzing " + side + " " + lobeName + " ...")
            for segmentProperty in self.segmentProperties:
                segmentName = f"{segmentProperty['name']} {side}"
                sourceSegID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
                sourceSeg = self.outputSegmentation.GetSegmentation().GetSegment(sourceSegID)
                newSegId = self.outputSegmentation.GetSegmentation().AddEmptySegment(segmentName + " " + lobeName,segmentName,segmentProperty['color'])
                newSeg = self.outputSegmentation.GetSegmentation().GetSegment(newSegId)
                newSeg.DeepCopy(sourceSeg)
                newSeg.SetName(segmentName + " " + lobeName)                
                self.subtractSegmentFromSegment(self.outputSegmentation, "right lower lobe", segmentName + " " + lobeName)                
                self.subtractSegmentFromSegment(self.outputSegmentation, "right middle lobe", segmentName + " " + lobeName)                
                self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(newSeg.GetName(),True)

            lobeName = "middle lobe"
            side = "right"
            self.showProgress("Analyzing " + side + " " + lobeName + " ...")
            for segmentProperty in self.segmentProperties:
                segmentName = f"{segmentProperty['name']} {side}"
                sourceSegID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
                sourceSeg = self.outputSegmentation.GetSegmentation().GetSegment(sourceSegID)
                newSegId = self.outputSegmentation.GetSegmentation().AddEmptySegment(segmentName + " " + lobeName,segmentName,segmentProperty['color'])
                newSeg = self.outputSegmentation.GetSegmentation().GetSegment(newSegId)
                newSeg.DeepCopy(sourceSeg)
                newSeg.SetName(segmentName + " " + lobeName)                
                self.subtractSegmentFromSegment(self.outputSegmentation, "right upper lobe", segmentName + " " + lobeName)                
                self.subtractSegmentFromSegment(self.outputSegmentation, "right lower lobe", segmentName + " " + lobeName)                
                self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(newSeg.GetName(),True)

            lobeName = "lower lobe"
            side = "right"
            self.showProgress("Analyzing " + side + " " + lobeName + " ...")
            for segmentProperty in self.segmentProperties:
                segmentName = f"{segmentProperty['name']} {side}"
                sourceSegID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
                sourceSeg = self.outputSegmentation.GetSegmentation().GetSegment(sourceSegID)
                newSegId = self.outputSegmentation.GetSegmentation().AddEmptySegment(segmentName + " " + lobeName,segmentName,segmentProperty['color'])
                newSeg = self.outputSegmentation.GetSegmentation().GetSegment(newSegId)
                newSeg.DeepCopy(sourceSeg)
                newSeg.SetName(segmentName + " " + lobeName)                
                self.subtractSegmentFromSegment(self.outputSegmentation, "right upper lobe", segmentName + " " + lobeName)                
                self.subtractSegmentFromSegment(self.outputSegmentation, "right middle lobe", segmentName + " " + lobeName)                
                self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(newSeg.GetName(),True)

            lobeName = "upper lobe"
            side = "left"
            self.showProgress("Analyzing " + side + " " + lobeName + " ...")
            for segmentProperty in self.segmentProperties:
                segmentName = f"{segmentProperty['name']} {side}"
                sourceSegID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
                sourceSeg = self.outputSegmentation.GetSegmentation().GetSegment(sourceSegID)
                newSegId = self.outputSegmentation.GetSegmentation().AddEmptySegment(segmentName + " " + lobeName,segmentName,segmentProperty['color'])
                newSeg = self.outputSegmentation.GetSegmentation().GetSegment(newSegId)
                newSeg.DeepCopy(sourceSeg)
                newSeg.SetName(segmentName + " " + lobeName)                
                self.subtractSegmentFromSegment(self.outputSegmentation, "left lower lobe", segmentName + " " + lobeName)                
                self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(newSeg.GetName(),True)

            lobeName = "lower lobe"
            side = "left"
            self.showProgress("Analyzing " + side + " " + lobeName + " ...")
            for segmentProperty in self.segmentProperties:
                segmentName = f"{segmentProperty['name']} {side}"
                sourceSegID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
                sourceSeg = self.outputSegmentation.GetSegmentation().GetSegment(sourceSegID)
                newSegId = self.outputSegmentation.GetSegmentation().AddEmptySegment(segmentName + " " + lobeName,segmentName,segmentProperty['color'])
                newSeg = self.outputSegmentation.GetSegmentation().GetSegment(newSegId)
                newSeg.DeepCopy(sourceSeg)
                newSeg.SetName(segmentName + " " + lobeName)                
                self.subtractSegmentFromSegment(self.outputSegmentation, "left upper lobe", segmentName + " " + lobeName)                
                self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(newSeg.GetName(),True)
       
            # cleanup lobe masks in output segmentation
            for lobeName in ['right upper lobe', 'right middle lobe', 'right lower lobe', 'left upper lobe', 'left lower lobe' ]:
                sourceSegID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(lobeName)
                sourceSeg = self.outputSegmentation.GetSegmentation().RemoveSegment(sourceSegID)
                
        # Cleanup
        self.showStatusMessage('Cleaning up ...')
        self.maskLabelColorTable = self.maskLabelVolume.GetDisplayNode().GetColorNode()
        slicer.mrmlScene.RemoveNode(self.maskLabelVolume)
        slicer.mrmlScene.RemoveNode(self.maskLabelColorTable)
        allModelNodes = slicer.util.getNodes('vtkMRMLModelNode*').values()
        for ctn in allModelNodes:
          #logging.info('Name:>' + ctn.GetName()+'<')
          teststr = ctn.GetName()
          if 'SegmentEditorSurfaceCutModel' in teststr:
            #logging.info('Found:' + ctn.GetName())
            slicer.mrmlScene.RemoveNode(ctn)
                #break        
        allMarkupNodes = slicer.util.getNodes('vtkMRMLMarkupsFiducialNode*').values()
        for ctn in allMarkupNodes:
          #logging.info('Name:>' + ctn.GetName()+'<')
          teststr = ctn.GetName()
          if teststr == "C":
            #logging.info('Found:' + ctn.GetName())
            slicer.mrmlScene.RemoveNode(ctn)
                #break               

        # Compute quantitative results
        self.showProgress("Creating result tables ...")
        self.createResultsTable()

        self.showStatusMessage('Calculating statistics ...')
        self.calculateStatistics()
        self.showStatusMessage('Creating special table ...')
        self.createCovidResultsTable()
        self.createEmphysemaResultsTable()

        # turn visibility of subregions off if created
        if self.areaAnalysis == True: 
            for segmentProperty in self.segmentProperties:
                for side in ['left', 'right']:
                    for region in ['ventral', 'dorsal','upper','middle','lower']: 
                            segmentName = f"{segmentProperty['name']} {side} {region}"
                            segID = self.outputSegmentation.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
                            sourceSeg = self.outputSegmentation.GetSegmentation().GetSegment(segID)
                            self.outputSegmentation.GetDisplayNode().SetSegmentVisibility(sourceSeg.GetName(),False)
                        
        # Update progress value
        self.progress = 99
        self.showProgress("Processing complete.")
        slicer.app.processEvents()
        if self.showProgressBar: 
            self.progressbar.close()
        stopTime = time.time()
        logging.info('Processing completed in {0:.2f} seconds'.format(stopTime-startTime))
        print('Processing completed in {0:.2f} seconds'.format(stopTime-startTime))

    def createMaskedVolume(self, keepMaskLabelVolume=False):
        self.showStatusMessage('Creating masked volume ...')
        maskLabelVolume = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLabelMapVolumeNode')

        rightLeftLungSegmentIds = vtk.vtkStringArray()
        rightLeftLungSegmentIds.InsertNextValue(self.rightLungMaskSegmentID)
        rightLeftLungSegmentIds.InsertNextValue(self.leftLungMaskSegmentID)
        slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(self.inputSegmentation, rightLeftLungSegmentIds, maskLabelVolume, self.inputVolume)

        fillValue = -3000  # self.inputVolume.GetImageData().GetScalarRange()[0]  # volume's minimum value
        maskVolumeArray = slicer.util.arrayFromVolume(maskLabelVolume)

        if not self.lungMaskedVolume:
            self.lungMaskedVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Lung masked volume")
            self.lungMaskedVolume.CreateDefaultDisplayNodes()

        ijkToRas = vtk.vtkMatrix4x4()
        self.inputVolume.GetIJKToRASMatrix(ijkToRas)
        self.lungMaskedVolume.SetIJKToRASMatrix(ijkToRas)
        self.lungMaskedVolume.GetDisplayNode().CopyContent(self.inputVolume.GetDisplayNode())

        import numpy as np
        inputVolumeArray = slicer.util.arrayFromVolume(self.inputVolume)
        maskedVolumeArray = np.copy(inputVolumeArray)
        maskedVolumeArray[maskVolumeArray==0] = fillValue
        slicer.util.updateVolumeFromArray(self.lungMaskedVolume, maskedVolumeArray)

        if keepMaskLabelVolume:
            return maskLabelVolume
        else:
            maskLabelColorTable = maskLabelVolume.GetDisplayNode().GetColorNode()
            slicer.mrmlScene.RemoveNode(maskLabelVolume)
            slicer.mrmlScene.RemoveNode(maskLabelColorTable)

    def createThresholdedSegments(self, maskLabelVolume):
 
        self.showStatusMessage('Creating thresholded segments ...')

        # Create color table to store segment names and colors
        segmentLabelColorTable = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLColorTableNode')
        segmentLabelColorTable.SetTypeToUser()
        segmentLabelColorTable.NamesInitialisedOn()
        segmentLabelColorTable.SetAttribute("Category", "Segmentations")
        numberOfSegments = len(self.segmentProperties)*2
        segmentLabelColorTable.SetNumberOfColors(numberOfSegments+1)
        segmentLabelColorTable.GetLookupTable().SetRange(0, numberOfSegments)
        segmentLabelColorTable.GetLookupTable().SetNumberOfTableValues(numberOfSegments+1)
        segmentLabelColorTable.SetColor(0, "Background", 0.0, 0.0, 0.0, 0.0)

        # Create numpy array to store segments
        import numpy as np
        maskVolumeArray = slicer.util.arrayFromVolume(maskLabelVolume)
        inputVolumeArray = slicer.util.arrayFromVolume(self.inputVolume)
        segmentArray = np.zeros(inputVolumeArray.shape, np.uint8)
        thresholds = self.thresholds
        segmentLabelValue = 0

        # set low emphysema threshold to lowest possible value in maskLabelVolume to avoid missing some very dark bullae
        logging.info('Low emphysema threshold automatically adjusted to: ' + str(self.inputVolume.GetImageData().GetScalarRange()[0]))
        thresholds['thresholdBullaLower'] = self.inputVolume.GetImageData().GetScalarRange()[0]
       

        
        for side in ["right", "left"]:
            maskLabelValue = 1 if side == "right" else 2
            for segmentProperty in self.segmentProperties:
                segmentLabelValue += 1
                segmentName = f"{segmentProperty['name']} {side}"
                r, g, b = segmentProperty['color']
                segmentLabelColorTable.SetColor(segmentLabelValue, segmentName, r, g, b, 1.0)
                lowerThresholdName, upperThresholdName = segmentProperty["thresholds"]
                segmentArray[np.logical_and(
                    maskVolumeArray == maskLabelValue,
                    inputVolumeArray >= thresholds[lowerThresholdName],
                    inputVolumeArray < thresholds[upperThresholdName])] = segmentLabelValue

        # Create temporary labelmap volume from numpy array
        segmentLabelVolume = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLabelMapVolumeNode')
        slicer.util.updateVolumeFromArray(segmentLabelVolume, segmentArray)
        ijkToRas = vtk.vtkMatrix4x4()
        self.inputVolume.GetIJKToRASMatrix(ijkToRas)
        segmentLabelVolume.SetIJKToRASMatrix(ijkToRas)
        segmentLabelVolume.CreateDefaultDisplayNodes()
        segmentLabelVolume.GetDisplayNode().SetAndObserveColorNodeID(segmentLabelColorTable.GetID())

        # Import labelmap volume to segmentation
        if not self.outputSegmentation:
            self.outputSegmentation = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "Lung analysis segmentation")
            self.outputSegmentation.CreateDefaultDisplayNodes()
            segmentationDisplayNode = self.outputSegmentation.GetDisplayNode()
            segmentationDisplayNode.SetOpacity3D(0.2)
            segmentationDisplayNode.SetOpacity2DFill(0.5)
            segmentationDisplayNode.SetOpacity2DOutline(0.2)
        else:
            self.outputSegmentation.GetSegmentation().RemoveAllSegments()
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(segmentLabelVolume, self.outputSegmentation)
        
        # Remove small islands
        # Create temporary segment editor to get access to effects
        logging.info('Creating temporary segment editor ... ')
        segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
        segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
        segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
        segmentEditorWidget.setSegmentationNode(self.outputSegmentation)
        segmentEditorWidget.setSourceVolumeNode(maskLabelVolume)
        for side in ["right", "left"]:
              maskLabelValue = 1 if side == "right" else 2
              for segmentProperty in self.segmentProperties:
                  segmentName = f"{segmentProperty['name']} {side}"
                  if segmentProperty["removesmallislands"] == "yes":
                      logging.info('Removing small islands in  ' + segmentName)
                      segmentEditorNode.SetSelectedSegmentID(segmentName)
                      segmentEditorWidget.setActiveEffectByName("Islands")
                      effect = segmentEditorWidget.activeEffect()
                      effect.setParameter("MinimumSize","1000")
                      effect.setParameter("Operation","REMOVE_SMALL_ISLANDS")
                      effect.self().onApply()
        # Delete temporary segment editor
        logging.info('Deleting temporary segment editor ... ')
        segmentEditorWidget = None
        slicer.mrmlScene.RemoveNode(segmentEditorNode)    


        # Cleanup
        slicer.mrmlScene.RemoveNode(segmentLabelVolume)
        slicer.mrmlScene.RemoveNode(segmentLabelColorTable)

    def showTable(self, tableNode):
        currentLayout = slicer.app.layoutManager().layout
        layoutWithTable = slicer.modules.tables.logic().GetLayoutWithTable(currentLayout)
        slicer.app.layoutManager().setLayout(layoutWithTable)
        slicer.app.applicationLogic().GetSelectionNode().SetActiveTableID(tableNode.GetID())
        slicer.app.applicationLogic().PropagateTableSelection()

#
# LungCTAnalyzerTest
#

class LungCTAnalyzerTest(ScriptedLoadableModuleTest):
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
        self.test_LungCTAnalyzer1()

    def test_LungCTAnalyzer1(self):
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

        # Test the module logic
        logic = LungCTAnalyzerLogic()
        logic.inputVolume = inputVolume
        logic.inputSegmentation = lungMaskSegmentation
        logic.rightLungMaskSegmentID = lungMaskSegmentation.GetSegmentation().GetSegmentIdBySegmentName("right lung")
        logic.leftLungMaskSegmentID = lungMaskSegmentation.GetSegmentation().GetSegmentIdBySegmentName("left lung")

        self.delayDisplay('Processing starts.')
        logic.process() # 3D
        self.delayDisplay('Processing ends.')

        self.delayDisplay('Test passed')
