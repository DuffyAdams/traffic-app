#!/bin/bash
set -e

echo "Downloading go-pmtiles for Linux x86_64..."
wget -qO go-pmtiles.tar.gz https://github.com/protomaps/go-pmtiles/releases/latest/download/go-pmtiles_Linux_x86_64.tar.gz

echo "Extracting pmtiles..."
tar -xzf go-pmtiles.tar.gz
chmod +x pmtiles

echo "Creating public/maps directory if it doesn't exist..."
mkdir -p traffic-app/public/maps

echo "Extracting San Diego PMTiles..."
DATE=$(date +%Y%m%d)
./pmtiles extract "https://build.protomaps.com/${DATE}.pmtiles" traffic-app/public/maps/sandiego.pmtiles --bbox=-117.6,32.5,-116.7,33.5

echo "Cleanup..."
rm go-pmtiles.tar.gz pmtiles

echo "Done! San Diego map data downloaded to traffic-app/public/maps/sandiego.pmtiles."
