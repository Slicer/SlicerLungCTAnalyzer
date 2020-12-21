# Lung CT Analyzer

Lung CT Analyzer is a 3D Slicer extension for segmentation and spatial reconstruction of infiltrated, emphysematic and collapsed lung areas in CT scans. 

<b>Introduction</b><br>
The extent of pulmonary infiltrations as well as the presence of areas like emphysema or bullae are usually analyzed visually in CT scans. 
Abnormalities can not be quantified in numbers or milliliters and thus it is difficult to objectively compare results.  
This especially crucial in the light of the current COVID-19 pandemia with high case loads of patients with severe lung infiltrations, who need meticulous follow up over time.   
The aim of this project (Lung CT Analyzer, LCTA) was to develop a software program that enables three-dimensional segmentation of lung CT data and calculate individual volumes of pulmonary infiltrates and emphysema. 
3D Slicer (1) is an established and freely available 3D imaging platform for scientific use. Therefore, 3D Slicer was chosen as development platform and the inbuild Python as script language.   
<br>
<b>Video (Overview Lung CT Analyzer):</b> <br>
https://www.youtube.com/watch?v=0plsoy94hFE<br>
<br>
<br>
<b>Installation Tutorial</b><br>
This is new 3D Slicer extension which needs to be manually installed. It's an easy process. Please follow these steps:  
<ul>
<li>Start 3D Slicer</li>
<li>From the "Welcome" page, select "Install Slicer Extensions" </li>
<li>The "Extension Manager" will open.</li>
<li>Choose the "Install extensions" Tab of the "Extension Manager"</li>
<li>Search and install the extension described here: "Lung CT Analyzer"</li>
<li>Restart 3D Slicer</li>
</ul>
<br>
Now you should have two new entries in your "Modules" dropdown under "Chest imaging platform": "Lung CT Segmenter" and "Lung CT Analyzer". If you want to update to the latest development version of CT Lung Analyzer, please reinstall the extension from the "Extension Manager".<br>   
<br>
<br>
<b>Operation Tutorial</b><br>

Step 1: Start 3D Slicer
<ul>
<li>Start 3D Slicer</li>
<li>Load a DICOM chest CT dataset</li>
</ul>

Step 2: Run <b>Lung CT Segmenter</b> to create lung masks
<ul>
<li>Select the 'Lung CT Segmenter' extension. It can be found in 3D Slicer under the 'Chest Imaging Platform' category </li>
<li>Pick the input volume (required): Select a high resolution lung images series of the presently loaded DICOM CT data set  </li>
<li>Press the "Start" button</li>
<li>Follow the instructions on the screen, the manual procedures are simple and straightforward</li>
<li>Place three markers on the right lung, axial view (red slice)</li>
<li>Place three markers on the right lung, coronal view</li>
<li>Place three markers on the left lung axial view (red slice)</li>
<li>Place three markers on the left lung, coronal view</li>
<li>Place one marker on the trachea, axial view</li>
<li>Watch temporary lung masks being created on the display</li>
<li>Place additional markers if needed</li>
<li>If the temporary masks fit well, press 'Apply" and produce permanent mask segmentations.</li>
<li>In noisy or weak datasets you may want to adopt the volmetric threshold range (hidden in "Advanced"). If you get mask leakages please thst the maximum value down to -400. </li>
  
</ul>

Step 3: Run <b>Lung CT Analyzer</b>

<ul>
<li>Select the 'Lung CT Analyzer' extension. It can be found in 3D Slicer under the 'Chest Imaging Platform' category </li>
<li>Pick the input volume (required): Select a high resolution lung images series of the presently loaded DICOM CT data set  </li>
<li>Pick the 'Right lung mask' segmentation (required) </li>
<li>Pick the 'Left lung mask' segmentation (required)</li>
<li>Adjust the thresholds for areas of interest.</li>
<li>Check 'Include COVID-19 evaluation' if you want to do produce an affected / funtional volume (CovidQ) evaluation. Evaluation phase. Not for clinical decision making.</li>
<li>Press 'Compute results'</li>
</ul>

<b>Questions ? </b><br>
The best way to ask questions is using the Slicer forum (https://discourse.slicer.org/), go "Support", create a topic, mention "@rbumm" or add the "lungctanalyzer" keyword. I recommend to do both. 
<br>
<br>

<b>Details</b><br>
The software uses freely definable threshold ranges to identify five regions of interest: "Bulla/emphysema","Inflated","Infiltrated", "Collapsed" and "Lung Vessel". 
Segments are generated using 3DSlicer's segment editor "Threshold" function and the volume of each segment is calculated by using 3DSlicer's "Segment statistics" function. 
The results are then superimposed to the CT 2D views in standard colors: "Bulla" = black, "Inflated" = blue, "Infiltrated" = yellow, "Collapsed" = pink and "Vessel" = red. 
In addition, spatial reconstruction (3D) of the diseased lung segments is available. The total results of the segmentation include:<br>
<br>
<i>Total lung volume (100%)<br>
Right lung volume (% of total lung volume)<br>
Left lung volume (% of total lung volume)<br>
Functional right lung volume (inflated, % of right lung volume)<br>
Functional left lung volume (inflated, % of left lung volume)<br>
Functional total lung volume (inflated, % of total lung volume)<br>
Affected right lung volume (infiltrated + collapsed right volume, % of right lung volume)<br>
Affected left lung volume (infiltrated + collapsed left volume, % of left lung volume) <br>
Affected total lung volume (infiltrated + collapsed total volume, % of total lung volume) <br>
CovidQ (COVID-19 quotient: total affected lung volume [ml] /  functional lung volume [ml]) <br></i><br>
Vessel volume is subtracted from right lung volume, left lung volume and total lung volume to compensate for this anatomic compartment.
Intrapulmonary airways are not yet measured by LCTA and are not compensated for in the results. <br>
<br>
<b>First Results</b><br>
If used with sensible thresholds, LCTA is feasible, easy to use and reproducible. Spacial reconstruction of the segments yield impressive visual results.  Running LCTA only takes 5-6 seconds, running LCTA with 3D reconstruction takes about 1-2  minutes. LCTA has been developed and tested with 3D Slicer V 4.11.200930. 

<b>Limitations</b><br>
Lung volumes represent areas within the lung masks only. This induces a marginal volume error. 
Lung vessels have a thin infiltration-like parenchyma cover around them. This induces a small volume error.  
CovidQ has not been clinically evaluated yet. Do not base treatment decisions on that value.  
3D Slicer is not FDA approved. It is the users responsibility to ensure compliance with applicable rules and regulations. 
See also: https://www.slicer.org/wiki/CommercialUse<br>
<br>
<b>Version history</b><br>
V 1.0<br>
<ul>
<li>Initial version</li>
</ul>
V 1.1<br>
<ul>
<li>right and left lung mask drop down segment selectors added</li>
<li>processing routine checks existence and name of 'Right lung mask' and 'Left lung mask'</li>
</ul>
V 2.0 <br>
<ul>
<li>code made efficient and modular - thanks Andras Lasso (PERK)</li>
<li>real-time volume rendering</li>
<li>immediate updated of the color categorization, both in 2D and 3D (using colormaps and volume rendering)</li>
<li>better GUI</li>
</ul>
V 2.1 <br>
<ul>
<li>New extension "Lung CT Segmenter" created from https://github.com/rbumm/SlicerLungMaskGenerator</li>
<li>Improvements of lung segmenter module by Andras Lasso (PERK)</li>
</ul>
(1) https://www.slicer.org/
<br>
<br>
Ideas and realization: Rudolf Bumm (KSGR) and Andras Lasso (PERK)<br>
<br>
The code presented here is distributed under the Apache license (https://www.apache.org/licenses/LICENSE-2.0).<br> 
<br>

<b>Screenshots:</b> <br>
<br>
![alt text](https://github.com/rbumm/SlicerLungCTAnalyzer/blob/master/Screenshots/LungCTAnalyzerGUI.jpg?raw=true)
<br>
<br>
Graphical user interface
<br>
<br>
![alt text](https://github.com/rbumm/SlicerLungCTAnalyzer/blob/master/Screenshots/LungCTAnalyzerCovid19Result.jpg?raw=true)
<br>
<br>
CT Lung Analyzer with COVID-19 result table
<br>
Image reference: from COVID-19 patient under surveillance, published with patient's permission.<br>
<br>
<br>
<b>Citations</b><br>
<br>
For publications please include this text (modifying the initial part to describe your use case):<br>
"We performed a volumetric analysis and/or visualization in 3D Slicer (http://www.slicer.org) via the Lung CT Analyzer project (https://github.com/rbumm/SlicerLungCTAnalyzer/)"
<br>
<br>
<br>
Impressum: Prof. Rudolf Bumm, Department of Surgery, Kantonsspital Graubünden (KSGR), Loestrasse 170, Chur, Switzerland
<br>
