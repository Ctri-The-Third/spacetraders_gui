
// click an inspect
function fetch_block(query, return_div_symbol) {
    //alert("fetching " + query + " into " + return_div_symbol);
    url = "/query/" + query
    const parser = new DOMParser();

    // alert both these parameters]
    console.log("[" + query + "] [" + return_div_symbol + "]")


    fetch(url, { method: 'GET', headers: { 'Authorization': 'Bearer ' + localStorage.getItem("SpaceTradersToken") } })
        .then(response => response.text())
        .then(html => {
            var parsedHtml = parser.parseFromString(html, 'text/html');
            // Handle the JSON blob response here
            document.getElementById(return_div_symbol).innerHTML = html;
            reinit();
            console.log(svg)
        }).catch(error => console.error(error));


}
function reinit() {
    //alert("init");
    svg = document.getElementById("systemView");
    circles = svg.getElementsByTagName("circle");
    //on mouseover change the contents of 'controlinput' to the id of the circle
    for (var i = 0; i < circles.length; i++) {
        circles[i].addEventListener("mouseover", function () {
            if (this.id != "") { document.getElementById("controlinput").value = this.id; }
        });
        circles[i].addEventListener("click", function () {
            if (this.id != "") {
                fetch_block(this.id, "object_summary");
            }
        });
    }
}

reinit()
//load a json blob and draw circles based on its content



function highlight(id) {

    var el = document.getElementById(id);
    el.classList.add("highlighted");

    setTimeout(function () {
        el.classList.remove("highlighted");
    }, 2000);
}
