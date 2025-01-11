import os
import requests
import ee
import rasterio
from rasterio.merge import merge
from glob import glob
import streamlit as st

# Initialize Earth Engine
def initialize_ee(project='ee-bordamit'):
    ee.Authenticate()
    ee.Initialize(project=project)

# Define a function to load the Area of Interest (AOI) from an Earth Engine asset
def load_aoi_from_gee(aoi_path="users/your_username/your_asset_name"):
    # Load AOI from Earth Engine asset using the provided asset path
    aoi = ee.FeatureCollection(aoi_path)
    return aoi

# Load the Sentinel-2 image collection and filter by date and bounds
def load_sentinel_image_collection(aoi, start_date='2023-01-01', end_date='2023-01-31'):
    s2 = ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
    return s2.filterBounds(aoi).filterDate(start_date, end_date).mean()

# Compute NDVI for the given image collection
def compute_ndvi(image):
    return image.normalizedDifference(['B8', 'B4']).rename('NDVI')

# Clip the image to the Area of Interest (AOI)
def clip_image_to_aoi(image, aoi):
    return image.clip(aoi)

# Get download URL for a specific NDVI region
def get_download_url(ndvi_image, region):
    return ndvi_image.clip(region).getDownloadURL({'scale': 10, 'crs': 'EPSG:4326', 'filePerBand': False, 'format': 'GeoTIFF'})

# Function to download images from URLs
def download_images(download_urls, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    for i, url in enumerate(download_urls):
        if url:
            try:
                response = requests.get(url)
                response.raise_for_status()
                with open(os.path.join(output_folder, f"image_{i}.tif"), "wb") as f:
                    f.write(response.content)
                print(f"Downloaded image {i + 1}")
            except requests.exceptions.RequestException as e:
                print(f"Error downloading image {i+1}: {e}")

# Function to create a mosaic from a list of downloaded images
def mosaic_tif_images(folders, output_file):
    tif_files = [glob(os.path.join(folder, "*.tif")) for folder in folders]
    tif_files = [item for sublist in tif_files for item in sublist]

    src_files_to_mosaic = [rasterio.open(tif) for tif in tif_files]
    mosaic, out_trans = merge(src_files_to_mosaic)

    out_meta = src_files_to_mosaic[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "count": mosaic.shape[0],
        "width": mosaic.shape[2],
        "height": mosaic.shape[1],
        "transform": out_trans
    })

    with rasterio.open(output_file, "w", **out_meta) as dest:
        dest.write(mosaic)

    print(f"Mosaic created successfully at {output_file}")

# Main function to execute the entire process
def process(aoi, num_splits, start_date='2023-01-01', end_date='2023-01-31', output_folder="downloaded_images"):
    initialize_ee()

    # Load the AOI and Sentinel image
    image = load_sentinel_image_collection(aoi, start_date, end_date)
    
    # Compute NDVI and clip to the AOI
    ndvi = compute_ndvi(image)
    ndvi_clipped = clip_image_to_aoi(ndvi, aoi)

    # Split the AOI into sub-regions (you can modify this part as per your needs)
    sub_regions = split_bounds(aoi.geometry(), num_splits)

    # Get download URLs for each sub-region
    download_urls = [get_download_url(ndvi_clipped, region) for region in sub_regions]

    # Download images from the URLs
    download_images(download_urls, output_folder)

    # Create a mosaic from the downloaded images
    mosaic_tif_images([output_folder], "mosaic_output.tif")
    return "Mosaic created successfully!"

# Define Streamlit UI components
def streamlit_ui():
    st.title('Sentinel-2 NDVI Processor')

    # User inputs for AOI selection from predefined options
    aoi_name = st.selectbox("Select Area of Interest (AOI)", ["Botad", "Other_AOI_Name"])  # Example options

    # Load AOI from GEE based on selection
    aoi_path = f"users/your_username/{aoi_name}"  # Update with your Earth Engine username and asset name
    aoi = load_aoi_from_gee(aoi_path)

    st.text(f"AOI '{aoi_name}' selected.")

    # User inputs for date range and number of splits
    start_date = st.date_input("Start Date", value='2023-01-01')
    end_date = st.date_input("End Date", value='2023-01-31')
    num_splits = st.slider("Number of Sub-regions", min_value=1, max_value=10, value=5)

    # Start processing on button click
    if st.button('Process'):
        st.text('Processing your data...')
        result = process(aoi, num_splits, start_date=str(start_date), end_date=str(end_date))
        st.text(result)
        
        st.text('Download the generated mosaic: ')
        st.download_button('Download Mosaic', "mosaic_output.tif", file_name="mosaic_output.tif")

if __name__ == "__main__":
    streamlit_ui()
