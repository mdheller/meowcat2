/* app.js */

//--------------------------------------------------------------------
/* auto update */

function pollForAutoUpdate(url, mrts){
    //console.log("pollForAutoUpdate url=" + url + " mrts=" +mrts);
    $.ajax({
        url: url,
        method: "GET",
        dataType: "json",
    }).done(function(ts){
        console.log("pollForAutoUpdate ts=" + toString(ts));
        var ts2 = ts.ts;
        if (ts2>mrts) {
            /* refresh page */
            location.reload(true);
        } else {
            /* try again 10 s later */
            setTimeout(
                function(){pollForAutoUpdate(url, mrts)}, 
                10000);
        }
    }); 
}    

//--------------------------------------------------------------------
/* starring messages */

function starClicked(mid){
    console.log("starClicked mid=" + mid);
    var url = "/x/star/" + mid;
    $.ajax({
        url: url,
        method: "POST",
        dataType: "json"
    }).done(function(d){
        
        
    });     
}    



//--------------------------------------------------------------------

//end