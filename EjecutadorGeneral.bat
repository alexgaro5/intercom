@echo off

set /p nombre=Archivo a ejecutar, sin "intercom_" ni ".py", solo el nombre: 
set /p canal=¿Uno o dos canales?: 
python intercom_%nombre%.py -c %canal%