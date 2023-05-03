import pandas as pd
import pyodbc
import plotly
import plotly.express as px


def showData(module,date_ini,date_fin):
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

    fecha = []
    valor_antes = []
    valor_despues = []

    #Procesado para dejar disponibles solo los valores numéricos
    for i in range(len(rows)):
        aux = str(df['Valor'][i])

        if aux.find('NEW VALUE') != -1:
           aux = aux.replace('NEW VALUE = ','').replace('OLD VALUE = ','')
           aux = aux.replace(' ','').replace(' ','')
           aux = aux.split(',')
           
           if aux[0][0] >= '0' and aux[0][0] <= '9':
                fecha.append(df['Fecha'][i])
                valor_antes.append(float(aux[0]))
                valor_despues.append(float(aux[1]))

    datafr = pd.DataFrame()
    datafr['date'] = fecha
    datafr['val_antes'] = valor_antes
    datafr['val_desps'] = valor_despues

    fig = px.line(datafr,x='date',y=['val_antes','val_desps'], markers=True )

    fig.update_layout(
        autosize=False,
        width=700,
        height=700,
        )
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)