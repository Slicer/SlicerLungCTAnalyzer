cmake_minimum_required(VERSION 3.13.4)

project(LungCTAnalyzer)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/rbumm/SlicerLungCTAnalyzer#lung-ct-analyzer")
set(EXTENSION_CATEGORY "Chest Imaging Platform")
set(EXTENSION_CONTRIBUTORS "Rudolf Bumm (KSGR Chur Switzerland)")
set(EXTENSION_DESCRIPTION "Extension for segmentation and spatial reconstruction of infiltrated and collapsed areas in chest CT examinations.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/rbumm/SlicerLungCTAnalyzer/master/LungCTAnalyzer.png")
set(EXTENSION_SCREENSHOTURLS "https://user-images.githubusercontent.com/18140094/98554410-f5ddd600-22a0-11eb-9196-b9223c8ada3f.jpg https://user-images.githubusercontent.com/18140094/98554914-9207dd00-22a1-11eb-9bae-7f537a765cc3.jpg https://user-images.githubusercontent.com/18140094/98555178-e6ab5800-22a1-11eb-8cbf-7dfa3e346b43.jpg")
set(EXTENSION_DEPENDS "PyTorch SegmentEditorExtraEffects SurfaceWrapSolidify") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(LungCTAnalyzer)
add_subdirectory(LungCTSegmenter)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
