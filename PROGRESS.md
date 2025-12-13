# Documentation of Journey

### The Idea
This will serve as a documentation of my journey where I will write my current ideas, challenges and solutions that I encounter for the entirety of this project.

### Journey
I am currently reading the book Meteorology Today An Introduction to Weather, Climate, and the Environment and I will list all the metrics provided by the Israeli Meteorological Service (IMS) to make it easier to see which ones are used to engineer important features discussed in the book or in meteorological papers.

### IMS Weather Station Variables List:
| Hebrew Variable (Original) | Variable Abbr. | English Equivalent | Description / Standard Units |
| :--- | :--- | :--- | :--- |
| לחץ בגובה התחנה | BP | Barometric Pressure (Station Pressure) | Pressure measured at the station's elevation. ($\text{hPa}$) |
| קרינה מפוזרת | DiffR | Diffuse Solar Radiation | Solar energy reaching the ground indirectly after scattering by the atmosphere. ($\text{W}/\text{m}^2$) |
| קרינה גלובלית | Grad | Global Radiation (Global Horizontal Irradiance) | Total solar energy (direct $+$ diffuse) reaching a horizontal surface. ($\text{W}/\text{m}^2$) |
| קרינה ישירה | NIP | Direct Normal Irradiance ($\text{DNI}$) | Solar energy reaching the surface directly from the sun's disk. ($\text{W}/\text{m}^2$) |
| כמות גשם | Rain | Precipitation Amount ($\text{Total}$) | Accumulated rainfall since the last measurement. ($\text{mm}$) |
| לחות יחסית | RH | Relative Humidity | Water vapor content as a percentage of the amount needed for saturation. ($\%$) |
| סטיית התקן של כיוון הרוח | STDwd | Standard Deviation of Wind Direction | Measures the variability/gustiness of the wind direction. ($\text{deg}$) |
| טמפרטורה יבשה | TD | Dry Bulb Temperature (Air Temperature) | The standard air temperature measured by a thermometer. ($\text{°C}$) |
| טמפרטורה מקסימלית | TDmax | Maximum Air Temperature | Highest $\text{TD}$ recorded over a period (e.g., 24 hours). ($\text{°C}$) |
| טמפרטורה מינימלית | TDmin | Minimum Air Temperature | Lowest $\text{TD}$ recorded over a period. ($\text{°C}$) |
| טמפרטורה ליד הקרקע | TG | Ground Surface Temperature | Temperature measured just above or at the ground level. ($\text{°C}$) |
| זמן סיום 10 דקות מקסימליות | Time | Time of Maximum 10-Minute Reading | Time of day ($\text{hhmm}$) when the maximum of a short-term variable was recorded. |
| כיוון הרוח | WD | Wind Direction | Direction from which the wind is blowing (in degrees from North). ($\text{deg}$) |
| כיוון המשאב העליון | WDmax | Maximum Wind Direction | Direction recorded at the time of maximum wind gust. ($\text{deg}$) |
| מהירות הרוח | WS | Wind Speed | Average speed of the wind over a sampling period. ($\text{m}/\text{s}$) |
| מהירות רוח 10 דקות מקסימלית | WS10mm | Maximum 10-Minute Wind Speed | Highest 10-minute average wind speed recorded. ($\text{m}/\text{s}$) |
| מהירות רוח דקות מקסימלית | WS1mm | Maximum 1-Minute Wind Speed | Highest 1-minute average wind speed recorded. ($\text{m}/\text{s}$) |
| מהירות המשאב העליון | WSmax | Maximum Wind Gust Speed | The highest instantaneous wind speed or gust recorded. ($\text{m}/\text{s}$) |
| גשם בדקה | Rain\_1\_Min | 1-Minute Precipitation Amount | Rainfall accumulation recorded over a 1-minute interval. ($\text{mm}$) |