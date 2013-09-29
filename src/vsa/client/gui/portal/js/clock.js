function showClock() {
        var Digital=new Date()
        var hours=Digital.getHours()
        var minutes=Digital.getMinutes()
        var seconds=Digital.getSeconds()
        var dn=""
//      var dn="AM"
//      if (hours>12){
//              dn="PM"
//              hours=hours-12
//      }
        if (hours==0)
                hours=12
        if (minutes<=9)
                minutes="0"+minutes
        if (seconds<=9)
                seconds="0"+seconds
        var ctime="<b><font face='Verdana' color='#8000FF'>"+hours+":"+minutes+":"+seconds+" "+dn+"</font></b>"
        document.getElementById("tick2").innerHTML=ctime
}

function loadClock() {
        showClock()
        setInterval("showClock()",1000)
}
