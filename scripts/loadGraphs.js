function fetchGraphsPage(return_div_symbol) {
    url = "/graph_template/"
    const parser = new DOMParser();

    // alert both these parameters]


    fetch(url, { method: 'GET', headers: { 'Authorization': 'Bearer ' + localStorage.getItem("SpaceTradersToken") } })
        .then(response => response.text())
        .then(html => {
            var parsedHtml = parser.parseFromString(html, 'text/html');
            // Handle the JSON blob response here
            document.getElementById(return_div_symbol).innerHTML = html;
        }).catch(error => console.error(error))
        .finally(() => {

            fetch("/graph_content/", { method: 'GET', headers: { 'Authorization': 'Bearer ' + localStorage.getItem("SpaceTradersToken") } })
                .then(response => response.json()).catch(error => console.error(error))

                // returns a json object of keys and values. The key is the id of the div to be updated, and the value is the plotly grpah to be rendered 
                .then(data => {
                    // Use Plotly to plot the data
                    data;
                    console.log(data);
                    var layout = {
                        title: 'Credits per hour',
                        xaxis: {
                            title: 'Time'
                        },
                        yaxis: {
                            title: 'Credits'
                        },
                        template: "plotly_dark"
                    };

                    Plotly.newPlot('creditsOverTime', data, layout).then(function () {
                        // Once the plot is made, apply the theme
                        var update = {
                            'layout.template': 'plotly_dark'
                        };
                        Plotly.relayout('creditsOverTime', update);
                    });;
                })
                .catch(error => console.error(error))
        }).catch(error => console.error(error))
}


