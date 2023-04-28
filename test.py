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
        rows=cursor.fetchall()
        cursor.close()

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
 
    

@app.route('/',methods = ['GET'])
def home():
    return render_template('home.html')

#Ver detalle de un modulo en un dia 
@app.route('/moduleDetails/<module>/<date_ini>/<date_fin>',methods=['GET'])
def detalleModulo(module,date_ini,date_fin):
    cursor = connection.cursor()
    fecha_inicial = date_ini 
    fecha_final   = date_fin 
    cursor.execute("SELECT j.Date_Time, j.Module_Description, j.Desc2 FROM dbo.Journal as j WHERE j.Date_Time >= ?  and j.Date_Time <=  ?  and j.Module = ? ORDER BY j.Date_Time ASC",(fecha_inicial,fecha_final,module))
    rows=cursor.fetchall()
    
    cursor.close()
    #Graficar tomando como x la fecha y como y la cantidad de cambios
    df = pd.DataFrame()
    df['Fecha'] = [r[0] for r in rows]
    df['Valor'] = [r[2] for r in rows]

    #Necesito solo los valores numericos
    for i in range(len(df['Valor'])):

        aux = str(df['Valor'][i])
        aux = aux.replace('NEW VALUE = ','').replace('OLD VALUE = ','')
        aux = aux.split(',')
        #Si no tiene un numero, saltar
        if len(aux) == 1 and aux[0].isnumeric() == True:
            continue
        num = int(aux[0])
        df['Valor'][i] = num
    
    fig = px.line(df,x='Fecha', y='Valor', title='Detalle de modulo')
    fig.update_layout(
        autosize=False,
        width=700,
        height=700,
        )
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template('moduleDetails.html',rows=rows,mod = module, date_ini = date_ini, date_fin = date_fin, graphJSON=graphJSON)
    


@app.route('/frequencyUsers',methods=['GET','POST'])
def frequencyUsers():
    if request.method == 'POST':
        fecha_inicial = request.form['entry-date-ini'] + " 00:00:00"
        fecha_final   = request.form['entry-date-fin'] + " 23:59:59"
        area          = request.form['areas']

        cursor = connection.cursor()
        cursor.execute("SELECT ch.Desc1, COUNT(ch.desc1) as Apariciones FROM ChangeUser as ch WHERE ch.Area=? AND ch.Date_time >= ? and ch.date_time <= ? GROUP BY ch.Desc1 ORDER BY COUNT(ch.desc1) DESC",area,fecha_inicial,fecha_final)
        datos = cursor.fetchall()
        cursor.close()

        #Diccionario para luego poder graficar con plotly
        diccionario = dict()
        for d in datos:
            diccionario[d[0]] = d[1]
        
        #Grafico con plotly
        fig = px.pie(values=diccionario.values(), names=diccionario.keys(), title='Frecuencia de usuarios')
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(
            autosize=False,
            width=700,
            height=700,
            )
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


        return render_template('frequencyUsers.html',areas=global_areas,datos=datos, graphJSON=graphJSON, area=area, fecha_ini=fecha_inicial, fecha_fin=fecha_final)
    else:
        return render_template('frequencyUsers.html',areas=global_areas)
    


@app.route('/areasymodulos', methods = ["GET","POST"])
def areasymodulos():  
    res = ""
    if request.method == "POST":
        option = request.form["opciones"]
        res = global_dictAreas[option]
  
    return render_template('areasymodulos.html',list_areas=global_areas,dictt = global_dictAreas,res=res)

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
def frecuentesChangeArea():

    if request.method == 'POST':
        #Obtener datos del formulario
        area          = request.form["areas"]
        fecha_inicial = request.form["entry-date-ini"] + " 00:00:00"
        fecha_final   = request.form["entry-date-fin"] + " 23:59:59"

       #Consulta a la base de datos
        cursor = connection.cursor()
        
        #Selección de los 10 modulos mas frecuentes
        cursor.execute("SELECT top(10) j.Module, j.Module_Description, COUNT (j.Module) as conteo FROM dbo.ChangeUser as j WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? GROUP BY j.Module, j.Module_Description ORDER BY conteo DESC", area,fecha_inicial,fecha_final)
        data = cursor.fetchall()   
        cursor.close()

       
        #Creamos dataframe 
        df = pd.DataFrame()
        df['Modulo'] = [d[0] for d in data]
        df['Descripcion'] = [d[1] for d in data]
        df['Cambios'] = [d[2] for d in data]

        #Grafico con plotly
        fig = px.bar(df, x='Modulo', y="Cambios", color="Modulo", title="Frecuencia de modulos")
        fig.update_layout(
            autosize=False,
            width=700,
            height=700,
            )
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)




       

        return render_template('frecuentesChangeArea.html',areas=global_areas,data=data,graphJSON=graphJSON, area=area, fecha_ini=fecha_inicial, fecha_fin=fecha_final)
    else:
        return render_template('frecuentesChangeArea.html',areas=global_areas)
    

@app.route('/frecuentesJournal',methods=['GET','POST'])
def frecuentesJournal():

    if request.method == 'POST':
        area          = request.form["opciones"]
        fecha_inicial = request.form["entry-date-ini"] + " 00:00:00"
        fecha_final   = request.form["entry-date-fin"] + " 23:59:59"

        cursor = connection.cursor()  
        cursor.execute("SELECT CONVERT(date,j.Date_Time) as Dia, j.Module, j.Module_Description, COUNT (j.Module) as conteo FROM dbo.Journal as j WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? GROUP BY CONVERT(date,j.Date_Time),j.Module, j.Module_Description ORDER BY conteo DESC", area,fecha_inicial,fecha_final)

        data = cursor.fetchall()   
        cursor.close()           

        return render_template('frecuentesJournal.html',areas=global_areas,data=data)
    else:
        return render_template('frecuentesJournal.html', areas=global_areas)


global_areas = getListOfAreas() #Variable global con las areas de la planta
global_dictAreas , global_dictModule = getDictOfAreas() #Variable global con el diccionario de areas y modulos

if __name__ == '__main__':
    
    #app.run(debug=True, use_debugger=False, use_reloader=False) #Use production server
    app.run(debug=True) #Use development server
    