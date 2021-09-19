# Panorama Image Processor

The new panorama image processor container using the algoritm developed by CTO.

## Tools

Two tools areavailable, `speed` and `process`.
`Speed` calulates the speed for the panorma processor based on the dequeuing of the
processing quue, and gives gives an estimation of the speed and the ETA.
`Process` will fill the processing queue based on missions in te azure container store.
One azure container contains all the missions for a year.