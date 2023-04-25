from flask import Flask, render_template, request
import pyodbc
import plotly
import plotly_express as px
import pandas as pd
import json


server = 'D6SMTCV2'

database= 'DB004'

username = 'favalos'
password = 'favalos'
connection = pyodbc.connect(f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}')



app = Flask(__name__)



@app.route('/moduleSearch',methods=['GET','POST'])
def moduleSearch():
    if request.method == 'POST':
        modulo = request.form['entry-modulo']
        fecha_inicial = request.form['entry-date-ini'] + " 00:00:00"
        fecha_final = request.form['entry-date-fin'] + " 23:59:59"
        print(modulo,fecha_inicial,fecha_final)
        cursor = connection.cursor()
        cursor.execute( "SELECT CONVERT(date, j.Date_time) as Dia,COUNT (j.Module) as NumCambios FROM DB004.dbo.Journal as j WHERE j.Date_Time >= ? and j.Date_Time <= ?  and j.Module = ? GROUP BY CONVERT(date, j.Date_time) ORDER BY Dia",fecha_inicial,fecha_final,modulo)
        #cursor.execute("SELECT * FROM dbo.JournalChangeLavado as j WHERE j.Date_Time >= ? and j.Date_Time <= ? and j.Attribute not like '%NALM' and J.Attribute not like 'ALARMS%' and j.Module = ? ORDER BY j.Date_Time",(fecha_inicial,fecha_final,modulo))
        rows=cursor.fetchall()

        cambios=0

        for r in rows:
            aux = str(r)
            aux = aux.replace('(','').replace(')','')
            aux = aux.split(',')
            num = int(aux[1])
            cambios+=num
            
        
        numdatos=cambios

        return render_template('moduleSearch.html',rows=rows,numdatos=numdatos,areas=global_areas)
    else:
        return render_template('moduleSearch.html', areas=global_areas)
    
@app.route('/test',methods=['GET'])
def test():
    df = pd.DataFrame({
      'Fruit': ['Apples', 'Oranges', 'Bananas', 'Apples', 'Oranges', 
      'Bananas'],
      'Amount': [4, 1, 2, 2, 4, 5],
      'City': ['SF', 'SF', 'SF', 'Montreal', 'Montreal', 'Montreal']
   })
    fig = px.bar(df, x='Fruit', y='Amount', color='City', barmode='group')
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)   
    return render_template('test.html', graphJSON=graphJSON)
    

@app.route('/',methods = ['GET'])
def home():
    return render_template('home.html')

#Ver detalle de un modulo en un dia 
@app.route('/moduleDetails/<module>/<date>',methods=['GET'])
def detalleModulo(module,date):
    cursor = connection.cursor()
    fecha_inicial = date + " 00:00:00"
    fecha_final = date + " 23:59:59"
    cursor.execute("SELECT * FROM dbo.Journal as j WHERE j.Date_Time >= ?  and j.Date_Time <=  ?  and j.Module = ? ORDER BY j.Date_Time ASC",(fecha_inicial,fecha_final,module))
    rows=cursor.fetchall()
    return render_template('moduleDetails.html',rows=rows,mod = module, date = date)
    
@app.route('/analisis_lavado',methods = ['GET'])
def analisis_lavado():
    
    return render_template('analisis_lavado.html')


@app.route('/areasymodulos', methods = ["GET","POST"])
def areasymodulos():
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM dbo.AreasYModulos")
    data = cursor.fetchall()

    areas = []
    for d in data:
            aux = str(d)
            aux = aux.replace('(','').replace(')','').replace("'",'')
            aux = aux.split(',')
            areas.append(aux[0])


    areaaa = set(areas)
    res = ""
    if request.method == "POST":
        option = request.form["opciones"]
        res = global_dictAreas[option]
  
    return render_template('areasymodulos.html',areas=areaaa,dictt = global_dictAreas,res=res)

def getDictOfAreas():
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM dbo.AreasYModulos")
    data = cursor.fetchall()
    
    diccionarioArea = dict() 
    diccionarioModulo = dict()
    for dd in data:
        area = dd[0]
        modulo = dd[1]
        modulo_description = dd[2]
        
        if area in diccionarioArea.keys(): #Si area esta en el diccionario
            diccionarioArea[area].append(modulo)
        else:
            diccionarioArea[area] = []
            diccionarioArea[area].append(modulo)

        if modulo in diccionarioModulo.keys():
            diccionarioModulo[modulo].append(modulo_description)
        else:
            diccionarioModulo[modulo] = []
            diccionarioModulo[modulo].append(modulo_description)
    cursor.close()

    return diccionarioArea, diccionarioModulo

#Lista de las áreas de la planta
def getListOfAreas():
    Areas = []
    cursor = connection.cursor()
    cursor.execute("SELECT DISTINCT Area FROM dbo.AreasYModulos")
    datos = cursor.fetchall()
    for data in datos:
        Areas.append(data[0])
    cursor.close()
    return Areas
    


@app.route('/frecuentesChangeArea',methods=['GET','POST'])
def modulosFrecuentesporArea():

    if request.method == 'POST':
        area = request.form["areas"]
        fecha_inicial = request.form["entry-date-ini"]
        fecha_final = request.form["entry-date-fin" ]

        cursor = connection.cursor()
        if (fecha_inicial == fecha_final):
            cursor.execute("SELECT CONVERT(date,j.Date_Time) as Dia, j.Module, j.Module_Description, COUNT (j.Module) as conteo FROM dbo.ChangeUser as j WHERE j.Area = ? and j.Date_Time = ?  GROUP BY CONVERT(date,j.Date_Time),j.Module,j.Module_Description ORDER BY conteo DESC", area,fecha_inicial)
        else:   
            cursor.execute("SELECT CONVERT(date,j.Date_Time) as Dia, j.Module, j.Module_Description, COUNT (j.Module) as conteo FROM dbo.ChangeUser as j WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? GROUP BY CONVERT(date,j.Date_Time),j.Module, j.Module_Description ORDER BY conteo DESC", area,fecha_inicial,fecha_final)

        data = cursor.fetchall()              

        return render_template('frecuentesChangeArea.html',areas=global_areas,data=data)
    else:
        return render_template('frecuentesChangeArea.html', areas=global_areas)
    

@app.route('/frecuentesJournal',methods=['GET','POST'])
def frecuentesJournal():

    if request.method == 'POST':
        area = request.form["opciones"]
        fecha_inicial = request.form["entry-date-ini"]
        fecha_final = request.form["entry-date-fin" ]

        cursor = connection.cursor()
        if (fecha_inicial == fecha_final):
            cursor.execute("SELECT CONVERT(date,j.Date_Time) as Dia, j.Module, j.Module_Description, COUNT (j.Module) as conteo FROM dbo.Journal as j WHERE j.Area = ? and j.Date_Time = ?  GROUP BY CONVERT(date,j.Date_Time),j.Module,j.Module_Description ORDER BY conteo DESC", area,fecha_inicial)
        else:   
            cursor.execute("SELECT CONVERT(date,j.Date_Time) as Dia, j.Module, j.Module_Description, COUNT (j.Module) as conteo FROM dbo.Journal as j WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? GROUP BY CONVERT(date,j.Date_Time),j.Module, j.Module_Description ORDER BY conteo DESC", area,fecha_inicial,fecha_final)

        data = cursor.fetchall()              

        return render_template('frecuentesJournal.html',areas=global_areas,data=data)
    else:
        return render_template('frecuentesJournal.html', areas=global_areas)


global_areas = getListOfAreas() #Variable global con las areas de la planta
global_dictAreas , global_dictModule = getDictOfAreas() #Variable global con el diccionario de areas y modulos

if __name__ == '__main__':
    
    app.run(debug = True)
    