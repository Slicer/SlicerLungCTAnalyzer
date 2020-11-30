cmake_minimum_required(VERSION 3.13.4)

project(SlicerCTLungAnalyzer)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/CTLungAnalyzer")
set(EXTENSION_CATEGORY "Chest Imaging Platform")
set(EXTENSION_CONTRIBUTORS "Rudolf Bumm (KSGR Chur Switzerland)")
set(EXTENSION_DESCRIPTION "This slicer extenstion will analyze the Hounsfield units of a given chest CT scan and produce five different segmentations: Bulla / emphysema, ventilated lung, infiltrated llung, collapsed lung and thoracic vessels. It allows a volume quantification as well as a spacial representation of the diseased lung regions. Furthermore, we introduce a new parameter - CovidQ - for an instant estimation of the severity of  infestation.  ")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/CTLungAnalyzer.png")
set(EXTENSION_SCREENSHOTURLS "http://www.example.com/Slicer/Extensions/CTLungAnalyzer/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(CTLungAnalyzer)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
