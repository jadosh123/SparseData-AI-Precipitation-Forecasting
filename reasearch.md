# Research

## Random Forest Spatial Interpolation Published 25 May 2020

A study conducted on the usage of Random Forest for Spatial Interpolation (RFSI) in comparison to classic deterministic methods like Regression kriging, Ordinary kriging, Random Forest and Random Forest for Spatial Prediction (RFsp) in three case studies. The first case study made use of synthetic data, i.e., simulations from normally distributed stationary random fields with a known semivariogram, for which ordinary kriging is known to be optimal. The second and third case studies evaluated the performance of the various interpolation methods using daily precipitation data for the 2016-2018 period in Catalonia, Spain, and mean dailty temperature for the year 2008 in Croatia.

Results of the synthetic case study showed that RFSI outperformed most simple deteministic interpolation techniques and had similar performance as inverse distance weighting and RFsp. As expected, kriging was the most accurate technique in the syntetic case study. In the precipitation and temperature case studies, RFSI mostly outperformed regression kriging, inverse distance weighting, random forest, and RFsp. Moreover, RFSI was substantially faster than RFsp, particularly when the training dataset was large and high-resolution prediction maps were made.

The study lists prior attempts at building a spatial random forests model or system to forecast precipitation, some approaches to include a geographic context into ML were to introduce longitude and latitude as covariates, as well as to use distance-to-coast and distance-to-closest dry grid cell as covariates along with precipitation at adjacent grid cells as covariates for downscaling precipitation using random forest

It is stated in the study that: to the best of our knowledge, none of the current approaches that aim to include geographical context in ML explicitly included the actual observations at the nearest locations of the prediction location as covariates. This is quite surprising because it seems to be a natural choice to include them; it is the very basis of kriging and most deterministic interpolation methods.

**My Explanation of the steps:**

1. Feature vector for each station S includes:

   1. Time-Series Features: Lag_Rain_t-1hr, Lag_pressure_t-6hr, etc. (Calculated at station S).
   2. Static Features: DEM_at_S, Slope_at_S, Dist_to_Coast_S.
   3. RFSI Spatial Features: Dis_to_Neighbor_1, Rain_at_Neighbor_1, Dist_to_Neighbor_2, etc.

2. Train the Random Forest or XGBoost on a dataset of the combined station's data so that the models learn the complex relationship between the physical features, time lags, and the local spatial context.

3. Create a feature grid where each cell would have the same length feature vector as the stations the model was trained on:

   1. For each cell add the spatial features like Dis_to_Neighbor_1, etc. up to N stations as done in training.
   2. Static Features: DEM_at_S, Slope_at_S, Dist_to_Coast_S
   3. Time-Series Features: Lag_Rain_t-1h, etc. (interpolated from the nearest N stations to match the original feature vectors).
      **Use fast interpolation methods like inverse distance weighting**

4. Use the trained Random Forest/XGBoost model to predict the precipitation forecast for each cell on the grid.

5. Validate model performance by comparing its predictions on the stations against the measurements at the stations, also compare interpolated results by the ML model against a holdout station inside the interpolated grid to evaluate the accuracy of the interpolation.
