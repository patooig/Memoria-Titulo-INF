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

    SQL = ( "SELECT j.Attribute,j.Desc1,COUNT(j.Attribute) as count "
            "FROM dbo.Journal as j "
            "WHERE j.Date_Time >= ?  and j.Date_Time <=  ?  and j.Module = ? "
            "GROUP BY j.Attribute, j.Desc1 "
            "ORDER BY count DESC"
            )
    
    cursor.execute(SQL,(fecha_inicial,fecha_final,module))
    rows=cursor.fetchall()
    cursor.close()

    df = pd.DataFrame()

    df['Attribute'] = [r[0] for r in rows]
    df['Desc1']     = [r[1] for r in rows]
    df['count']     = [r[2] for r in rows]

    #Set name of columns
    df.columns = ['Attribute','Desc1','count']

    #Find the uniques
    uniques_attributes = df['Attribute'].unique()

    #Create a dict with the uniques attributes and the value is the sum of the count
    dict_uniques = dict()
    for u in uniques_attributes:
        dict_uniques[u] = df[df['Attribute'] == u]['count'].sum()   
    
    len_dict = len(dict_uniques)

    return render_template('moduleDetails.html',
                           dictt = dict_uniques,
                           uniques_attributes=uniques_attributes,
                           len_dict=len_dict,
                           mod = module,
                           date_ini = date_ini,
                           date_fin = date_fin)
    

@app.route('/dashboard',methods=['GET','POST'])
def dashboard():
    if request.method == 'POST':
        #Obtener datos del formulario
        area          = request.form["areas"]
        fecha_inicial = request.form["entry-date-ini"] + " 00:00:00"
        fecha_final   = request.form["entry-date-fin"] + " 23:59:59"

        def users():
            cursor = connection.cursor()

            #Selección de los usuarios mas frecuentes
            SQL = ("SELECT ch.Desc1, COUNT(ch.desc1) as Apariciones "
                   "FROM ChangeUser as ch "
                   "WHERE ch.Area=? AND ch.Date_time >= ? and ch.date_time <= ? "
                   "GROUP BY ch.Desc1 "
                   "ORDER BY COUNT(ch.desc1) DESC"
                )
            
            cursor.execute(SQL,area,fecha_inicial,fecha_final)
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
                width=500,
                height=500,
                )
            graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            return graphJSON
        
        def modulesChange():
            cursor = connection.cursor()
            
            #Selección de los 10 modulos mas frecuentes
            SQL = ("SELECT top(10) j.Module, j.Module_Description, COUNT (j.Module) as conteo "
                   "FROM dbo.ChangeUser as j "
                   "WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? "
                   "GROUP BY j.Module, j.Module_Description "
                   "ORDER BY conteo DESC"

            )
            cursor.execute(SQL, area,fecha_inicial,fecha_final)
            data = cursor.fetchall()   
            cursor.close()

        
            #Creamos dataframe 
            df = pd.DataFrame()
            df['Modulo'] = [d[0] for d in data]
            df['Descripcion'] = [d[1] for d in data]
            df['Cambios'] = [d[2] for d in data]

            #Grafico con plotly
            fig = px.bar(df, x='Modulo', y="Cambios", color="Modulo", title="Top 10 módulos change")
            fig.update_layout(
                autosize=False,
                width=500,
                height=500,
                )
            graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            return graphJSON

        def modulesTodos():
            cursor = connection.cursor()
            SQL = ( "SELECT TOP(10) j.Module, j.Module_Description, COUNT (j.Module) as conteo "
                "FROM dbo.Journal as j "
                "WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? and j.Attribute not like 'Change' "
                "GROUP BY j.Module, j.Module_Description "
                "ORDER BY conteo DESC ")
            
            cursor.execute(SQL, area,fecha_inicial,fecha_final)
            data = cursor.fetchall()
            cursor.close()

                #Creamos dataframe 
            df = pd.DataFrame()
            df['Modulo'] = [d[0] for d in data]
            df['Descripcion'] = [d[1] for d in data]
            df['Cambios'] = [d[2] for d in data]

            #Grafico con plotly
            fig = px.bar(df, x='Modulo', y="Cambios", color="Modulo", title="Top 10 módulos alarm-event", pattern_shape="Modulo",labels=dict(x="Modulo", y="Cantidad", color="Modulo")) 
            fig.update_layout(
                autosize=False,
                width=500,
                height=500,
                )
            graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

            return graphJSON
        
        def lineaTemporalChange():
            cursor = connection.cursor()
            SQL = ("SELECT CONVERT(	date, j.date_time) as Fecha , COUNT(j.Ord) as Cambios "
                   "FROM dbo.ChangeUser as j "
                   "WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? "
                   "GROUP BY CONVERT(date, j.date_time) "
                   "ORDER BY Fecha ")
            
            cursor.execute(SQL, area,fecha_inicial,fecha_final)
            data = cursor.fetchall()
            cursor.close()

            #Creamos dataframe 
            df = pd.DataFrame()
            df['Fecha'] = [d[0] for d in data]
            df['Cambios'] = [d[1] for d in data]

            #Grafico con plotly
            fig = px.line(df, x='Fecha', y="Cambios", title="Cambios CHANGE por día")
            fig.update_layout(
                autosize=False,
                width=500,
                height=500,
                )
            graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            return graphJSON
        
        return render_template('dashboard.html',
                               areas=global_areas,
                               graphJSON=modulesChange(),
                               graphJSON2=lineaTemporalChange(),
                               graphJSON3=users(),
                               graphJSON4=modulesTodos())
    else:
        return render_template('dashboard.html',areas=global_areas)

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

def preprocesadoDashboard(datos):

    #DATOS GENERALES
    df_general = pd.DataFrame()
    
    data = []
    module = []
    module_description = []
    desc1 = []
    desc2 = []

    for d in datos:
        data.append(d[0])
        module.append(d[1])
        module_description.append(d[2])
        desc1.append(d[3])
        desc2.append(d[4])
    
    df_general['date'] = data
    df_general['module'] = module
    df_general['module_description'] = module_description
    df_general['desc1'] = desc1
    df_general['desc2'] = desc2

    #Agrupar por modulo
    freqModules = df_general.groupby(['module']).size()
    freqModules = freqModules.sort_values(ascending=False)
    #Obtener los 10 modulos con mas cambios
    freqModules = freqModules.index[:10]                        
    

    #Filtrar por los 10 modulos con mas cambios en un nuevo dataframe
    df2 = df_general[df_general['module'].isin(freqModules)]
    df2 = df2.groupby(['module','desc1']).size()
    #Crea un dataframe con los 10 modulos con mas cambios
    df2 = df2.to_frame()
    df2 = df2.reset_index()
    df2.columns = ['module','desc1','count']

    return df2
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
        SQL = (
            "SELECT top(10) j.Module, j.Module_Description, COUNT (j.Module) as conteo "
            "FROM dbo.ChangeUser as j "
            "WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? "
            "GROUP BY j.Module, j.Module_Description "
            "ORDER BY conteo DESC"
            )
        
        cursor.execute(SQL, area,fecha_inicial,fecha_final)
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

        return render_template('frecuentesChangeArea.html',
                               areas=global_areas,
                               data=data,
                               graphJSON=graphJSON,
                               area=area, 
                               fecha_ini=fecha_inicial, 
                               fecha_fin=fecha_final)
    else:
        return render_template('frecuentesChangeArea.html',
                               areas=global_areas)
    

@app.route('/frecuentesJournal',methods=['GET','POST'])
def frecuentesJournal():

    if request.method == 'POST':
        area          = request.form["area"]
        fecha_inicial = request.form["entry-date-ini"] + " 00:00:00"
        fecha_final   = request.form["entry-date-fin"] + " 23:59:59"

        cursor = connection.cursor()  

        SQL = ( "SELECT TOP(10) j.Module, j.Module_Description, COUNT (j.Module) as conteo "
                "FROM dbo.Journal as j "
                "WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? and j.Attribute not like 'Change' "
                "GROUP BY j.Module, j.Module_Description "
                "ORDER BY conteo DESC ")
        

        cursor.execute(  SQL, area,fecha_inicial,fecha_final)

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

        return render_template('frecuentesJournal.html',
                               areas=global_areas,
                               data=data,
                               graphJSON=graphJSON,
                               area=area,
                               fecha_ini=fecha_inicial,
                               fecha_fin=fecha_final
                               )
    else:
        return render_template('frecuentesJournal.html', 
                               areas=global_areas)


global_areas = getListOfAreas() #Variable global con las areas de la planta
global_dictAreas , global_dictModule = getDictOfAreas() #Variable global con el diccionario de areas y modulos

if __name__ == '__main__':
    
    #app.run(debug=True, use_debugger=False, use_reloader=False) #Use production server
    app.run(debug=True) #Use development server
    