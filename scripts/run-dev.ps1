Start-Process python "$PSScriptRoot\traffic_scraper.py"
Start-Process powershell "-NoExit -Command cd $PSScriptRoot\traffic-app; npm run dev"
