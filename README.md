# Lung CT Analyzer

Lung CT Analyzer is a 3D Slicer extension for segmentation and spatial reconstruction of infiltrated, emphysematic and collapsed lung areas in CT scans. 

<b>Introduction</b><br>
The extent of pulmonary infiltrations as well as the presence of areas like emphysema or bullae are usually analyzed visually in CT scans. 
Abnormalities can not be quantified in numbers or milliliters and thus it is difficult to objectively compare results.  
This especially crucial in the light of the current COVID-19 pandemia with high case loads of patients with severe lung infiltrations, who need meticulous follow up over time.   
The aim of this project (Lung CT Analyzer, LCTA) was to develop a software program that enables three-dimensional segmentation of lung CT data and calculate individual volumes of pulmonary infiltrates and emphysema. 
3D Slicer (1) is an established and freely available 3D imaging platform for scientific use. Therefore, 3D Slicer was chosen as development platform and the inbuild Python as script language.   
<br>
[Video Lung CT Segmenter](https://youtu.be/U9PUX-jLF0A) <br>
<br>
[Video Lung CT Analyzer] (https://youtu.be/JcgMnDhlknM) <br>
<br>
<br>
[Installation Tutorial]https://github.com/rbumm/SlicerLungCTAnalyzer/wiki/Installation<br>
<br>
<br>
[Operation Tutorial](https://github.com/rbumm/SlicerLungCTAnalyzer/wiki)</b><br>
<br>
<br>
<b>Questions ? </b><br>
The best way to ask questions is using the Slicer forum (https://discourse.slicer.org/), go "Support", create a topic, mention "@rbumm" or add the "lungctanalyzer" keyword. I recommend to do both. 
<br>
<br>

<b>Details</b><br>
The software uses freely definable threshold ranges to identify five regions of interest: "Bulla/emphysema","Inflated","Infiltrated", "Collapsed" and "Lung Vessel". 
Segments are generated using 3DSlicer's segment editor "Threshold" and "Grow from Seeds" function. The volume of each segment is calculated by using 3DSlicer's "Segment statistics" function. 
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
<br></i>

Comment: The AF-Q parameter was discontinued after realizing it´s non-linearity<br>

Vessel volume is subtracted from right lung volume, left lung volume and total lung volume to compensate for this anatomic compartment.
Intrapulmonary airways are not yet measured by LCTA and are not compensated for in the results. <br>
<br>
<b>First Results</b><br>
If used with sensible thresholds, LCTA is feasible, easy to use and reproducible. Spacial reconstruction of the segments yield impressive visual results.  Production of lung masks in the "Lung Segmenter" is done in about 2 minutes after defining a few fiducials on the right and left lung and one additional on the tracea.  Running LCTA itself  only takes 5-6 seconds, running LCTA with 3D reconstruction takes about 1-2  minutes. LCTA has been developed and tested with 3D Slicer V 4.11.200930. 

<b>Limitations</b><br>
Lung volumes represent areas within the lung masks only. This induces a marginal volume error. 
Lung vessels have a thin infiltration-like parenchyma cover around them. This induces a small volume error.  
3D Slicer is not FDA approved. It is the users responsibility to ensure compliance with applicable rules and regulations. 
See also: https://www.slicer.org/wiki/CommercialUse<br>
<br>


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
"We performed a volumetric analysis and/or visualization in [3D Slicer](http://www.slicer.org) via the [Lung CT Analyzer project](https://github.com/rbumm/SlicerLungCTAnalyzer/)"
<br>
<br>
This project is in active development and is not FDA approved
<br>
<br>
Impressum: Prof. Rudolf Bumm, Department of Surgery, Kantonsspital Graubünden (KSGR), Loestrasse 170, Chur, Switzerland
<br>
