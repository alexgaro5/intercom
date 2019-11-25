@echo off

set /p nombre=Archivo a ejecutar, sin "intercom_" ni ".py", solo el nombre: 
set /p canal=1 o 2 canales: 
python intercom_%nombre%.py -c %canal% -r 11025 -cb 8
PAUSE