# Lung CT Analyzer

Lung CT Analyzer is a 3D Slicer extension for lung, lobe and airway segmentation as well as spatial reconstruction of infiltrated, emphysematic and collapsed lung areas. 

<b>Introduction</b><br>
The extent of pulmonary infiltrations as well as the presence of areas like emphysema or bullae are usually analyzed visually in CT scans. 
Abnormalities can not be quantified in numbers or milliliters making it difficult to objectively compare results. In the current COVID-19 pandemia high case loads of patients with severe lung infiltrations, who need meticulous follow up over time, accumulate.   
The aim of this project (Lung CT Analyzer, LCTA) was to develop a software program that enables three-dimensional segmentation of lung CT data and calculate individual volumes of pulmonary infiltrates and emphysema. 
3D Slicer (1) is an established and freely available 3D imaging platform for scientific use. Therefore, 3D Slicer was chosen as development platform and the inbuild Python as script language.   
<br>
[Video Lung CT Segmenter](https://youtu.be/U9PUX-jLF0A) <br>
<br>
[Video Lung CT Analyzer](https://youtu.be/JcgMnDhlknM) <br>
<br>
[Installation Tutorial](https://github.com/rbumm/SlicerLungCTAnalyzer/wiki/Installation)<br>
<br>
[Operation Tutorial](https://github.com/rbumm/SlicerLungCTAnalyzer/wiki)</b><br>
<br>
<b>Questions ? </b><br>
The best way to ask questions is using the [Slicer forum](https://discourse.slicer.org/).  go "Support", create a topic, mention "@rbumm" or add the "lungctanalyzer" keyword. I recommend to do both. 
<br>

<b>Details</b><br>
Lung segmentation can be archieved by either placing a few markups on the lung or by using a deep learning lung and lobe segmentation algorithm (see below).
A sensitive and manually assisted growcut airway segmentation is supported. 
The Lung Analyzer uses thresholding and grow from seeds to identify five regions of interest: "Bulla/emphysema","Inflated","Infiltrated", "Collapsed" and "Lung Vessel". 
The volume of each segment is calculated by "Segment statistics". 
The results are then superimposed to 2D views in standard colors: "Bulla" = black, "Inflated" = blue, "Infiltrated" = yellow, "Collapsed" = pink and "Vessel" = red. 
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

Vessel volume is subtracted from lung volumes, intrapulmonary airways are not subtracted. <br>
<br>
LCTA has been developed and tested with 3D Slicer 5.03 stable.

<b>Limitations</b><br>
3D Slicer is not FDA approved. It is the users responsibility to ensure compliance with applicable rules and regulations. 
See also: https://www.slicer.org/wiki/CommercialUse<br>
<br>


(1) https://www.slicer.org/
<br>
<br>
Ideas and realization: Rudolf Bumm (KSGR) and Andras Lasso (PERK)<br>
The code presented here is distributed under the Apache license (https://www.apache.org/licenses/LICENSE-2.0).<br> 
<br>
<br>
Deep learning lung and lobe segmentation is realized by implementation of 'Lungmask' AI models and algorithms (https://github.com/JoHof/lungmask) with permission. 
<br>
Thank you Johannes Hofmanninger. 
<br>
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
Image data: COVID-19 patient under surveillance, with patient's permission.<br>
<br>
<b>Citations</b><br>
<br>
For publications please include this text (modifying the initial part to describe your use case):<br>
"We performed a volumetric analysis and/or visualization in 3D Slicer (http://www.slicer.org) via the Lung CT Analyzer project (https://github.com/rbumm/SlicerLungCTAnalyzer/)"
<br>
<br>
If you use the deep learning function from this software in your research, please cite: 
<br>
Hofmanninger, J., Prayer, F., Pan, J. et al. Automatic lung segmentation in routine imaging is primarily a data diversity problem, not a methodology problem. Eur Radiol Exp 4, 50 (2020). https://doi.org/10.1186/s41747-020-00173-2
<br>
<br>
This project is in active development and not FDA approved.
<br>
<br>
Impressum: Prof. Rudolf Bumm, Department of Surgery, Kantonsspital Graubünden (KSGR), Loestrasse 170, Chur, Switzerland
<br>
