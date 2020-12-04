# Lung CT Analyzer

Lung CT Analyzer is a 3D Slicer extension for segmentation and spatial reconstruction of infiltrated, emphysematic and collapsed lung areas in CT scans. 

<b>Aim </b><br>
The extent of pulmonary infiltrations as well as the presence of non-ventilated areas like emphysema or bullae are usually analyzed visually in CT scans. 
Abnormalities can not be quantified in numbers or milliliters and thus it is difficult to objectively compare results.  
This especially crucial in the light of the current COVID-19 pandemia, where we face high case loads of patients with severe lung infiltrations, who need meticulous follow up over time.   
The aim of this project was to develop a software program that enables three-dimensional segmentation of lung CT data and calculate individual volumes of pulmonary infiltrates and emphysema. 
3D Slicer (1) is an established an freely available 3D imaging platform for scientific use. Therefore, we chose 3D Slicer as our development platform and the inbuild Python as script language.   
<br>
<b>Video (Overview):</b> <br>
https://www.youtube.com/watch?v=0plsoy94hFE<br>
<br>
<br>
<b>Tutorial</b><br>

Step 1: Start 3D Slicer
<ul>
<li>Start 3D Slicer</li>
<li>Load a DICOM chest CT dataset</li>
</ul>

Step 2: Create lung masks 
https://github.com/rbumm/SlicerLungMaskGenerator

Alternate ways to create lung masks see -> Appendix.  
  
Step 3: Run Lung CT Analyzer

<ul>
<li>Select the 'Lung CT Analyzer' extension. It can be found in 3D Slicer under the 'Chest Imaging Platform' category </li>
<li>Pick the input volume (required): Select a high resolution lung images series of the presently loaded DICOM CT data set  </li>
<li>Pick the 'Right lung mask' segmentation (required) </li>
<li>Pick the 'Left lung mask' segmentation (required)</li>
<li>Adjust the thresholds for areas of interest.</li>
<li>Check 'Include COVID-19 evaluation' if you want to do produce an affected / funtional volume (CovidQ) evaluation. Evaluation phase. Not for clinical decision making.</li>
<li>Press 'Compute results'</li>
</ul>

<b>Details</b><br>
The software uses freely definable threshold ranges to identify five regions of interest: "Bulla/emphysema","Ventilated","Infiltrated", "Collapsed" and "Lung Vessel". 
Segments are generated using 3DSlicer's segment editor "Threshold" function and the volume of each segment is calculated by using 3DSlicer's "Segment statistics" function. 
The results are then superimposed to the CT 2D views in standard colors: "Bulla" = black, "Ventilated" = blue, "Infiltrated" = yellow, "Collapsed" = pink and "Vessel" = red. 
In addition, spatial reconstruction (3D) of the diseased lung segments is available. The total results of the segmentation include:<br>
<br>
<i>Total lung volume (100%)<br>
Right lung volume (% of total lung volume)<br>
Left lung volume (% of total lung volume)<br>
Functional right lung volume (ventilated, % of right lung volume)<br>
Functional left lung volume (ventilatzed, % of left lung volume)<br>
Functional total lung volume (ventilated, % of total lung volume)<br>
Affected right lung volume (infiltrated + collapsed right volume, % of right lung volume)<br>
Affected left lung volume (infiltrated + collapsed left volume, % of left lung volume) <br>
Affected total lung volume (infiltrated + collapsed total volume, % of total lung volume) <br>
CovidQ (COVID-19 quotient: total affected lung volume [ml] /  functional lung volume [ml]) <br></i><br>
Vessel volume is subtracted from right lung volume, left lung volume and total lung volume to compensate for this anatomic compartment.
Intrapulmonary airways are not yet measured by CTLA and are not compensated for in the results. <br>
<br>
<b>First Results</b><br>
If used with sensible thresholds, LCTA is feasible, easy to use and 100% reproducible. Spacial reconstruction of the segments yield impressive visual results.  Although the production of a right and left lung mask is still rather time consuming (15 min), running LCTA only takes 5-6 seconds, running LCTA with 3D reconstruction takes about 1-2  minutes. LCTA has been developed and tested with 3D Slicer V 4.11.200930. 

<b>Limitations</b><br>
Lung volumes represent areas within the lung masks only. This induces a marginal volume error. 
Lung vessels have a thin infiltration-like parenchyma cover around them. This induces a small volume error.  
CovidQ has not been clinically evaluated yet. Do NOT base and treatment decisions on that value alone.  
3DSlicer is NOT FDA approved. It is the users responsibility to ensure compliance with applicable rules and regulations. 
See also: https://www.slicer.org/wiki/CommercialUse

<b>Discussion</b><br>

<b>Upcoming features:</b><br> 
<br>
Quantitative ventrodorsal lung infiltrate analysis (effect of patient positioning)<br>
Fiduical placements in trachea, normal lung, COVID lung, vessel and calculating autothresholds<br>
Compensate for the "vessel infiltrate" error <br>
Compensate for the "lung airway volume " error <br>
Serial examinations<br>
<br>
<b>Version history</b><br>
<br>
V 1.0<br>
<ul>
<li>First version.</li>
</ul>
<br>
<br>
V 1.1<br>
<ul>
<li>right and left lung mask drop down segment selectors added.</li>
<li>processing routine checks existence and name of 'Right lung mask' and 'Left lung mask'</li>
</ul>
<br>
<br>
V 2.0 <br>
<ul>
<li>code made efficient and modular - thanks Andras Lasso (PERK)</li>
<li>real-time volume rendering</li>
<li>immediate updated of the color categorization, both in 2D and 3D (using colormaps and volume rendering)</li>
<li>better GUI</li>
</ul>
<br>
<br>
(1) https://www.slicer.org/
<br>
<br>
Idea and realization: Rudolf Bumm, Department of Surgery, Kantonsspital Graubünden (KSGR), Chur, Switzerland. <a href="mailto:rudolf.bumm@ksgr.ch">Email</a>  <br>
Source code optimizations: Andras Lasso (PERK)<br>
<br>
The code presented here is distributed under the Apache license (https://www.apache.org/licenses/LICENSE-2.0).<br> 
<br>
Contact: <br>
<br>
Rudolf Bumm<br>
rudolf.bumm@ksgr.ch<br>
<br>
Scientific-Networks Munich<br>
info@scientific-networks.com<br>

Images: <br>
<br>
Image from COVID-19 patient under surveillance, published with patient's permission.<br>
<br>
![screen1](https://user-images.githubusercontent.com/18140094/98554410-f5ddd600-22a0-11eb-9196-b9223c8ada3f.jpg)
<br>
![screen2](https://user-images.githubusercontent.com/18140094/98554914-9207dd00-22a1-11eb-9bae-7f537a765cc3.jpg)
<br>
![screen3](https://user-images.githubusercontent.com/18140094/98555178-e6ab5800-22a1-11eb-8cbf-7dfa3e346b43.jpg)

<br>
<b>Appendix</b> 
<br>
<br>
Step 2: Create lung masks by using the Segment Editor's 'Fill between Slices' function

<ul>
  <li>Open 3D Slicer's 'Segment Editor'</li>
  <li>Create a new segmentation node</li>
  <li>In this segmentation node, create two new segments. Call one 'Right lung mask', the other one 'Left lung mask'. Please enter the names with exactly one space between words, because the presence of these segments will later be checked using their names.</li>  
  <li>In the Segment Editor:  select 'Right lung mask' </li>
  <li>In the Segment Editor:  press 'Draw' </li>
  <li>Draw a few complete slices around the right lung in axial CT view (red slice) - top to down </li>
  <li>In the Segment Editor:  select 'Left lung mask' </li>
  <li>In the Segment Editor:  press 'Draw' </li>
  <li>Draw a few complete slices around the left lung in axial CT view (red slice) - top to down</li>
  <li>Then press 'Fill between Slices' in the Segment Editor. </li>
  <li>Press 'Initialize'</li>
  <li>Check the segmentation results, improve the results by maybe drawing a few more slices on the lungs if needed, finally press 'Apply'</li>
  <li>Ready. You have now created two lung masks and may proceed to step 3 </li>
</ul>
<br>  
Step 2 (alternate procedure): Create lung masks by using the Nvidea AIAA in the Segment editor
<ul>
  <li>description will follow</li>
</ul>
