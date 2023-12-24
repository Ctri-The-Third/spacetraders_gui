function fetchGraph(url, return_div_id) {

    fetch(url, { method: 'GET', headers: { 'Authorization': 'Bearer ' + localStorage.getItem("SpaceTradersToken") } })
        .then(response => response.json()).catch(error => console.error(error))

        // returns a json object of keys and values. The key is the id of the div to be updated, and the value is the plotly grpah to be rendered 
        .then(data => {
            console.log(data);
            // Use Plotly to plot the data
            var plotData = data.data;
            var plotLayout = data.layout
            var plotTitle = data.title
            console.log(data);

            document.getElementById(return_div_id).innerHTML = "";

            Plotly.newPlot(return_div_id, plotData, plotLayout).then(function () {
                // Once the plot is made, apply the theme
                var update = {
                    'layout.template': 'plotly_dark'
                };
                Plotly.relayout(plotTitle, update);
            });;
        })
        .catch(error => console.error(error))
}