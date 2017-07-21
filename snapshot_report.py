import time

def build_table_cols(td_list):
    td_items = []
    for item in td_list:
        td_cols = ['<td>'+str(col)+'</td>' for col in item]
        td_items.append('<tr>' + ' '.join(td_cols) + '</tr>')

    return " ".join(td_items)

def write_mail_content_html(filename, lockwaits, processlist, innodb_status_text):
    html_body = """
    <html><head>
<style>
.mytable table {
    width:100%%;
    margin:15px 0;
    border:0;
}
.mytable,.mytable th,.mytable td {
    font-size:0.95em;
    text-align:left;
    padding:4px;
    border-collapse:collapse;
}
.mytable th,.mytable td {
    border: 1px solid #ffffff;
    border-width:1px
}
.mytable th {
    border: 1px solid #cde6fe;
    border-width:1px 0 1px 0
}
.mytable td {
    border: 1px solid #eeeeee;
    border-width:1px 0 1px 0
}
.mytable tr {
    border: 1px solid #ffffff;
}
.mytable tr:nth-child(odd){
    background-color:#f7f7f7;
}
.mytable tr:nth-child(even){
    background-color:#ffffff;
}
.mytable2 th, .mytable2 td {
    border-width:1px 1 1px 1
}
</style>
    </head><body>
        <div>
        <h2>Lock Waits Info:</h2>
            <table class='mytable'>
              <tr>
                <th>trx_id</th>
                <th>role</th>
                <th>thread_id</th>
                <th>dbuser</th>
                <th>dbuser</th>
                <th>trx_state</th>
                <th>trx_operation_state</th>
                <th>trx_rows_locked</th>
                <th>trx_lock_structs</th>
                <th>trx_started</th>
                <th>duration</th>
                <th>lock_mode</th>
                <th>lock_type</th>
                <th>lock_table</th>
                <th>lock_index</th>
                <th>lock_data</th>
                <th>trx_query</th>
                <th>blocking_trx_id</th>
              </tr>
              %s
            </table>
        </div><br/>

        <div>
        <h2>Processlist Info:</h2>
            <table class='mytable'>
              <tr>
                <th>thread_id</th>
                <th>user</th>
                <th>host</th>
                <th>db</th>
                <th>command</th>
                <th>time</th>
                <th>state</th>
                <th>info</th>
              </tr>
              %s
            </table>
        </div><br/>

        <div>
        <h2>InnoDB Status:</h2>
            <table class='mytable mytable2'>
              <tr>
                <th>thread_id</th>
              </tr>
              <tr><td>
                %s
              </td></tr>
            </table>
        </div><br/>

    </body></html>
    """ % (
            build_table_cols(lockwaits),
            build_table_cols(processlist),
            innodb_status_text
        )
    # filename = time.strftime("%Y%m%d-%H%M%S") + filename
    fo = open(filename, "wb")
    fo.write(html_body)
    fo.close()
    return filename
    # return html_body