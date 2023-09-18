import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Select from 'react-select';
import { Bar } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, BarElement } from "chart.js";

const horizontalErrorBarsPlugin = {
    id: 'horizontalErrorBars',
    afterDraw: (chart) => {
        const ctx = chart.ctx;

        // Use the first dataset's meta to iterate over the bars
        const bars = chart.getDatasetMeta(0).data;

        bars.forEach((bar, index) => {
            // Find the dataset that is associated with this bar
            const dataset = chart.data.datasets.find(ds => !chart.getDatasetMeta(ds.index).hidden && ds.errorBars);

            if (!dataset) return;

            const data = dataset.data[index];
            const x = chart.scales.x.getPixelForValue(data);

            if (x <= 0) return;

            const errorBar = dataset.errorBars[index];
            const y = bar.getProps(['y'], true).y;

            ctx.save();
            ctx.strokeStyle = dataset.borderColor;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(x - errorBar.minus, y);
            ctx.lineTo(x + errorBar.plus, y);
            ctx.moveTo(x - errorBar.minus, y - 4);
            ctx.lineTo(x - errorBar.minus, y + 4);
            ctx.moveTo(x + errorBar.plus, y - 4);
            ctx.lineTo(x + errorBar.plus, y + 4);
            ctx.stroke();
            ctx.restore();
        });
    },
};

Chart.register(CategoryScale);
Chart.register(LinearScale);
Chart.register(BarElement);
Chart.register(horizontalErrorBarsPlugin);


function formatTime(minutes) {
    if (minutes === null) {
        return "N/A";
    }
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${String(hours).padStart(2, '0')}h${String(remainingMinutes).padStart(2, '0')}`;
}


function ControlPanel({ setOrigin, origin, setSelectedDest, setRoutes, setSummary, summary }) {
    const [cities, setCities] = useState([]);

    useEffect(() => {
        axios.get('http://localhost:8000/cities')
            .then(response => {
                // Transform the city list to an array of objects that react-select can use
                const cityOptions = response.data.map(city => ({ value: city, label: city }));
                setCities(cityOptions);
            })
            .catch(error => {
                console.error(error);
            });
    }, []);

    const handleChange = (selectedOption) => {
        setOrigin(selectedOption.value);
        setSelectedDest(null);
        setRoutes({});
        setSummary([])
    }

    const labels = summary.map(item => item.mode);
    const averageCO2 = summary.map(item => (item.CO2[0] + item.CO2[1]) / 2);
    const errorMinus = summary.map(item => (item.CO2[0] + item.CO2[1]) / 2 - item.CO2[0]);
    const errorPlus = summary.map(item => item.CO2[1] - (item.CO2[0] + item.CO2[1]) / 2);

    console.log(errorMinus);

    const data = {
        labels: labels,
        datasets: [
            {
                label: 'CO2 / pax',
                data: averageCO2,
                backgroundColor: 'orange',
                borderColor: 'red',
                hoverBackgroundColor: 'darkorange',
                errorBars: errorMinus.map((val, index) => ({
                    minus: val,
                    plus: errorPlus[index]
                }))
            }
        ]
    };

    const maxFromData = Math.max(...averageCO2);
    const maxFromErrorBars = averageCO2.reduce((max, val, i) => {
        return Math.max(max, val + errorPlus[i]);
    }, maxFromData);

    return (
        <div className="control-panel">
            <label htmlFor="origin">Origin City:</label>
            <Select
                id="origin"
                options={cities}
                onChange={handleChange}
                className='select'
                defaultValue={{ value: origin, label: origin }}
            />

            <div id="trip-info">
                Summary:
                <table className="table table-sm table-bordered">
                    <thead>
                        <tr>
                            <th>Mode</th>
                            <th>CO2 / pax</th>
                            <th>Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        {Array.isArray(summary) && summary.map(item => (
                            <tr key={item.mode}>
                                <td>{item.mode}</td>
                                <td>{item.CO2[0]} - {item.CO2[1]} kg</td>
                                <td>{formatTime(item.Time)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                <span>* CO2 for electric vehicle routes are based on countries' electricity emissions.</span>

                <hr />
                CO2 emissions / pax
                <div>
                    <Bar
                        data={data}
                        plugins={[horizontalErrorBarsPlugin]}
                        width={100}
                        height={200}
                        options={{
                            maintainAspectRatio: false,
                            indexAxis: 'y',
                            scales: {
                                x: {
                                    beginAtZero: true,
                                    suggestedMax: maxFromErrorBars,
                                },
                                y: {
                                    type: 'category',
                                    labels: ['flight', 'train (electric)', 'bus', 'car (2p,diesel)', 'car (2p,petrol)', 'car(2p,electric)']
                                }
                            }
                        }}
                    />
                </div>

            </div>
        </div>
    );
}

export default ControlPanel;
