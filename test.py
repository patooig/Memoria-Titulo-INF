from flask import Flask, render_template, request
import pyodbc
import plotly
import plotly_express as px
import pandas as pd
import json
import os 

import shutil

import hashlib



server = 'D6SMTCV2' #D6SMTCV2
database= 'DB004'
username = 'favalos'
password = 'favalos'
connection = pyodbc.connect(f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password};')
connection.autocommit = True

app = Flask(__name__)


df_general = None


def loadFilestoServer(filename,ruta_origen):
    

    ruta_destino = r'\\D6smtcv2\data'

    #Verificar si archivo ya existe en ruta destino
    if os.path.isfile(os.path.join(ruta_destino, filename)):
        print("El archivo ya existe en el servidor")
        return 2
    
    #Integridad de del archivo
    sha256_hash_origen = hashlib.sha256()

    with open(ruta_origen, 'rb') as archivo:
         for bloque in iter(lambda: archivo.read(4096), b''):
             sha256_hash_origen.update(bloque)
    archivo.close()
    print(f"El hash SHA256 del archivo .mdf es: {sha256_hash_origen.hexdigest()}")

    #Copiar archivo a servidor
    try:
        shutil.copy(ruta_origen, ruta_destino)
    except PermissionError as e:
        print(f"Error al mover el archivo: {e}")


    print("Archivo movido a servidor")

    #Ruta destino con nombre del archivo enviado
    ruta_destino = os.path.join(ruta_destino, filename)

    #Calculo de integridad del archivo en el servidor
    sha256_hash_destino = hashlib.sha256()
    with open(ruta_destino, 'rb') as archivo:
         for bloque in iter(lambda: archivo.read(4096), b''):
             sha256_hash_destino.update(bloque)
    archivo.close()
    
    print(f"El hash SHA256 del archivo .mdf es: {sha256_hash_destino.hexdigest()}")
    if sha256_hash_origen.hexdigest() == sha256_hash_destino.hexdigest():
        print("Integridad del archivo comprobada")
    return 1
    



@app.route('/loadFiles', methods = ['GET','POST'])
def loadFiles():
        if request.method == "POST":
            # file = request.files['filename'] #Capturo el archivo, PERO solo necesito el nombre
            # filename = file.filename #Nombre del archivo + extensión
            # print(filename) #Nombre del archivo + extensión

            # ruta_actual= os.path.dirname(os.path.abspath(__file__))
            # ruta_datos = os.path.join(ruta_actual, "datos")
            # ruta_datos = os.path.join(ruta_datos, filename)

            # res_load = loadFilestoServer(filename,ruta_datos)
            
            # if res_load == 1:
            #     cursor = connection.cursor()
            #     route = "EXEC [dbo].[Events_Copy] @filename  = " + filename + " "
            #     cursor.execute(route)

            cursor = connection.cursor()
            file = request.form['name_file']
            cursor.execute("EXEC [dbo].[Events_Copy] @filename  = '"  + file + "' ")

           
                #! RECALCULAR FECHAS DE INCIO Y FINAL DE BUSQUEDA
            return render_template('loadFiles.html', global_fecha_final=global_fecha_final, file=file)
        
        else:
            cursor = connection.cursor()
            SQL = ("{CALL ObtenerArchivosEnCarpeta}")
            cursor.execute(SQL)

            # Obtener los resultados
            resultados = []
            while cursor.nextset():
                try:
                    resultados.extend(cursor.fetchall())
                except pyodbc.ProgrammingError:
                    pass

            # Mostrar los resultados
            mdf_files = []
            sub_string = '20190101000000#201901312359'  #Nombre de archivo que no se debe mostrar, son los archivos originales de la base de datos
            for resul in resultados:
                if resul[0] is not None:
                    name_file = str(resul[0])
                    if name_file.endswith('.mdf') and not sub_string in name_file:
                        mdf_files.append(name_file)

        
            return render_template('loadFiles.html',global_fecha_final=global_fecha_final, mdf_files=mdf_files)

@app.route('/moduleSearch',methods=['GET','POST'])
def moduleSearch():
    if request.method == 'POST':
        modulo = request.form['entry-modulo']
        fecha_inicial = request.form['entry-date-ini'] + " 00:00:00"
        fecha_final = request.form['entry-date-fin'] + " 23:59:59"
        print(modulo,fecha_inicial,fecha_final)
        cursor = connection.cursor()
        cursor.execute( "SELECT CONVERT(date, j.Date_time) as Dia,COUNT (j.Module) as NumCambios FROM dbo.Journal as j WHERE j.Date_Time >= ? and j.Date_Time <= ?  and j.Module = ? GROUP BY CONVERT(date, j.Date_time) ORDER BY Dia",fecha_inicial,fecha_final,modulo)
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
@app.route('/moduleDetails/<module>/<type>/<date_ini>/<date_fin>',methods=['GET'])
def detalleModulo(module,type,date_ini,date_fin):
    cursor = connection.cursor()
    fecha_inicial = str(date_ini) 
    fecha_final   = str(date_fin) 
    
    
    if type.find('change') != -1:
        sql_extension = " AND j.Event_type like 'CHANGE' AND j.Attribute NOT LIKE 'ALARMS%' AND j.attribute NOT LIKE '%ALM'  "
    else:
        sql_extension = " AND j.Event_type not like 'CHANGE' "
        
    SQL = ( "SELECT j.Attribute,j.Desc1,COUNT(j.Attribute) as count "
                "FROM dbo.Journal as j "
                "WHERE j.Date_Time >= ?  and j.Date_Time <=  ?  and j.Module = ? " + sql_extension +
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
        print(df[df['Attribute'] == u]['count'].sum()   )
    len_dict = len(dict_uniques)

    return render_template('moduleDetails.html',
                           dictt = dict_uniques,
                           uniques_attributes=uniques_attributes,
                           len_dict=len_dict,
                           mod = module,
                           date_ini = date_ini,
                           date_fin = date_fin)
    



@app.route('/moduleDetails2/<module>/<date_ini>/<date_fin>',methods=['GET'])
def detalleModulo2(module,date_ini,date_fin):

    
    #Filtrar con el module, y el intervalo de fecha

    modulo = str(module)
    fecha_inicial = str(date_ini) 
    fecha_final   = str(date_fin) 

    new_df = df_general[df_general['Module'] == modulo]

    new_df = new_df.groupby(['Module', 'Attribute']).size().reset_index(name='Count')

    return render_template('moduleDetails2.html',
                        mod = module,
                        new_df=new_df,
                        date_ini = fecha_inicial,
                        date_fin = fecha_final)


    
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
                   "FROM dbo.ChangeUser as ch "
                   "WHERE ch.Area= ? AND ch.Date_time >= ? and ch.date_time <= ? "
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

        def eventosAlarmas():
            cursor = connection.cursor()
            SQL = ( "SELECT TOP(10) j.Module, j.Module_Description, COUNT (j.Module) as conteo "
                "FROM dbo.Journal as j "
                "WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? and j.Event_type not like 'Change' "
                "GROUP BY j.Module, j.Module_Description "
                "ORDER BY conteo DESC ")
            
            cursor.execute(SQL, area,fecha_inicial,fecha_final)
            data = cursor.fetchall()
            cursor.close()

                #Creamos dataframe 
            df = pd.DataFrame()
            df['Modulo'] = [d[0] for d in data]
            df['Descripcion'] = [d[1] for d in data]
            df['Cantidad'] = [d[2] for d in data]

            #Grafico con plotly
            fig = px.bar(df, x='Modulo', y="Cantidad", color="Modulo", title="Top 10 módulos alarm-event", ) 
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
            df['Fecha']   = [d[0] for d in data]
            df['Cambios'] = [d[1] for d in data]

            valor_promedio = df['Cambios'].mean()

            #Grafico con plotly
            fig = px.line(df, x='Fecha', y="Cambios", title="Eventos CHANGE")
            fig.add_hline(y=valor_promedio, line_dash="dot", annotation_text="Promedio")
            fig.update_layout(
                autosize=False,
                width=700,
                height=500,
                )
            graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            return graphJSON
        
        return render_template('dashboard.html',
                               areas=global_areas,
                               graphJSON=modulesChange(),
                               graphJSON2=lineaTemporalChange(),
                               graphJSON3=users(),
                               graphJSON4=eventosAlarmas(),
                               fecha_inicial=global_fecha_inicial,
                               fecha_final=global_fecha_final)
    else:
        return render_template('dashboard.html',
                               fecha_inicial=global_fecha_inicial,
                               fecha_final=global_fecha_final,
                               areas=global_areas)

@app.route('/frequencyUsers',methods=['GET','POST'])
def frequencyUsers():
    if request.method == 'POST':
        fecha_inicial = request.form['entry-date-ini'] + " 00:00:00"
        fecha_final   = request.form['entry-date-fin'] + " 23:59:59"
        area          = request.form['areas']

        cursor = connection.cursor()
        cursor.execute("SELECT ch.Desc1, COUNT(ch.desc1) as Apariciones FROM dbo.ChangeUser as ch WHERE ch.Area=? AND ch.Date_time >= ? and ch.date_time <= ? GROUP BY ch.Desc1 ORDER BY COUNT(ch.desc1) DESC",area,fecha_inicial,fecha_final)
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


        return render_template('frequencyUsers.html',
                               areas=global_areas,
                               datos=datos, 
                               graphJSON=graphJSON, 
                               area=area, 
                               fecha_ini=fecha_inicial,
                                fecha_fin=fecha_final,
                                fecha_inicial=global_fecha_inicial,
                               fecha_final=global_fecha_final)
    else:
        return render_template('frequencyUsers.html',
                               fecha_inicial=global_fecha_inicial,
                               fecha_final=global_fecha_final,
                               areas=global_areas)
    


@app.route('/areasymodulos', methods = ["GET","POST"])
def areasymodulos():  
    res = ""
    if request.method == "POST":
        option = request.form["opciones"]
        res = global_dictAreas[option]
  
    return render_template('areasymodulos.html',list_areas=global_areas,dictt = global_dictAreas,res=res)

def getDictOfAreas():
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM dbo.AreaModules2")
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
    cursor.execute("SELECT DISTINCT Area FROM dbo.AreaModules2")
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
            "SELECT top(10) j.Module, am.Module_Description, COUNT (j.Module) as conteo "
            "FROM DB004.dbo.ChangeUser as j , dbo.AreaModules2 as am  "
            "WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? AND am.Module = j.Module  "
            "GROUP BY j.Module, am.Module_Description "
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
                               fecha_fin=fecha_final,
                               fecha_inicial=global_fecha_inicial,
                               fecha_final=global_fecha_final)
    else:
        return render_template('frecuentesChangeArea.html',
                               fecha_inicial=global_fecha_inicial,
                               fecha_final=global_fecha_final,
                               areas=global_areas)
    
@app.route('/frecuentesJournal',methods=['GET','POST'])
def frecuentesJournal():

    if request.method == 'POST':
        area          = request.form["area"]
        fecha_inicial = request.form["entry-date-ini"] + " 00:00:00"
        fecha_final   = request.form["entry-date-fin"] + " 23:59:59"

        cursor = connection.cursor()  

        SQL = ( "SELECT TOP(10) j.Module, am.Module_Description, COUNT (j.Ord) as conteo "
                    "FROM dbo.Journal as j , dbo.AreaModules2 as am "
                    "WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? and j.Event_Type not like 'CHANGE' and j.Module = am.Module "
                    "GROUP BY j.Module, am.Module_Description "
                    "ORDER BY conteo DESC ")
        

        cursor.execute(SQL, area,fecha_inicial,fecha_final)

        data = cursor.fetchall()   
        cursor.close()           

        #Creamos dataframe 
        df = pd.DataFrame()
        df['Modulo']      = [d[0] for d in data]
        df['Descripcion'] = [d[1] for d in data]
        df['Cantidad de eventos']     = [d[2] for d in data]

        #Grafico con plotly
        fig = px.bar(df, x='Modulo', y="Cantidad de eventos", color="Modulo", title="Frecuencia de modulos")
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
                               fecha_fin=fecha_final,
                               fecha_inicial=global_fecha_inicial,
                               fecha_final=global_fecha_final,
                               )
    else:
        return render_template('frecuentesJournal.html', 
                               fecha_inicial=global_fecha_inicial,
                               fecha_final=global_fecha_final,
                               areas=global_areas)




@app.route('/frecuentesJournal2',methods=['GET','POST'])
def frecuentesJournal2():
    
    if request.method == 'POST':
        area          = request.form["area"]
        fecha_inicial = request.form["entry-date-ini"] + " 00:00:00"
        fecha_final   = request.form["entry-date-fin"] + " 23:59:59"

        SQL = ("SELECT j.Date_time,j.Module, am.Module_Description, j.Attribute , j.Desc1, j.Desc2 "
              "FROM dbo.Journal as j , dbo.AreaModules2 as am "
              "WHERE j.Area = ? and j.Date_Time >= ? and j.Date_Time <= ? and j.Event_Type not like 'CHANGE' and j.Module = am.Module ")
        
        df = pd.DataFrame(pd.read_sql_query(sql = SQL,
                                            con= connection ,
                                            params= ( area,fecha_inicial,fecha_final )) 
                                            , 
                                            columns=['Date_time','Module','Module_Description','Attribute','Desc1','Desc2']) 
        df['Date_time'] = pd.to_datetime(df['Date_time'])

        global df_general
        df_general = df

        df_count = df.groupby('Module')['Attribute'].count().reset_index(name='Eventos')
        df_count = df_count.sort_values('Eventos', ascending=False)

        # Agregar la columna 'Module_Description'
        df_count = df_count.merge(df[['Module', 'Module_Description']].drop_duplicates(), on='Module')

        #Selección de TOP 10
        df_count = df_count.head(10)

        #Grafico con plotly
        fig = px.bar(df_count, x='Module', y="Eventos", color="Module", title="Frecuencia de modulos")
        fig.update_layout(
            autosize=False,
            width=700,
            height=700,
            )
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

        return render_template('frecuentesJournal2.html',
                               areas=global_areas,
                               data=df_count,
                               datos=1,
                               graphJSON=graphJSON,
                               area=area,
                               fecha_ini=fecha_inicial,
                               fecha_fin=fecha_final
                            )

    else:
        return render_template('frecuentesJournal2.html', 
                               datos=0,
                               areas=global_areas)
    
        
        
def getFechaInicial():
        
    cursor = connection.cursor()  
    SQL = ("SELECT MIN(Date_Time) FROM dbo.Journal")
    cursor.execute(SQL)
    fecha_inicial = cursor.fetchone()[0]
    #Solo quiero los 10 primeros caracteres de la fecha
    fecha_inicial = str(fecha_inicial)[:10]
    print(fecha_inicial)
    cursor.close() 
    
    return fecha_inicial

def getFechaFinal():
            
    cursor = connection.cursor()  
    SQL = ("SELECT MAX(Date_Time) FROM dbo.Journal")
    cursor.execute(SQL)
    fecha_final = cursor.fetchone()[0]
    #Solo quiero los 10 primeros caracteres de la fecha
    fecha_final = str(fecha_final)[:10]
    print(fecha_final)
    cursor.close() 
    
    return fecha_final

global_areas = getListOfAreas() #Variable global con las areas de la planta
global_dictAreas , global_dictModule = getDictOfAreas() #Variable global con el diccionario de areas y modulos

def calcularNuevasFechas():
    global global_fecha_inicial
    global global_fecha_final
    
    global_fecha_inicial = getFechaInicial() #Variable global con la fecha inicial de la base de datos
    global_fecha_final = getFechaFinal() #Variable global con la fecha final de la base de datos
    
    return 
calcularNuevasFechas()

if __name__ == '__main__':
    
    #app.run(debug=True, use_debugger=False, use_reloader=False) #Use production server
    app.run( debug=True) #Use development server host='0.0.0.0'
   