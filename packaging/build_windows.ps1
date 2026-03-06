pip install pyinstaller

pyinstaller packaging/pyinstaller.spec

Compress-Archive -Path dist\dosidicus\* -DestinationPath Dosidicus-windows.zip
