suppressPackageStartupMessages(library(terra))
CH<-"/Users/hildamanzi/ICPAC-WORK/CHIRPS DATA/chirps_v3_ltn/chirps-v3.0.ltn.dekadal.1996-2025.gha_p05.tif"
CTD<-"/Users/hildamanzi/ICPAC-WORK/DOWNLOADED RASTER DATASETS/chirts_ltn"
KEN<-"/Users/hildamanzi/AEZ-COUNTRIES/gadm41_KEN_shp/gadm41_KEN_1.shp"
norm<-function(x) tolower(gsub("[^A-Za-z]","",x))
val<-read.csv("Cropyield-Data/ond_window_ltn_validation.csv",stringsAsFactors=FALSE)
v<-vect(KEN); v$k<-norm(v$NAME_1); val$k<-norm(val$county)
rain<-rast(CH); tmax<-rast(file.path(CTD,"chirts.ltn.dekadal.tmax.1996-2025.gha_p05.tif"))
tmin<-rast(file.path(CTD,"chirts.ltn.dekadal.tmin.1996-2025.gha_p05.tif"))
P<-T<-N<-matrix(NA,nrow(val),36)
for(i in seq_len(nrow(val))){ sel<-v[v$k==val$k[i],]; if(nrow(sel)==0) next; e<-ext(sel)+0.25
  P[i,]<-as.numeric(terra::extract(crop(rain,e),sel,fun=mean,na.rm=TRUE,ID=FALSE)[1,])
  T[i,]<-as.numeric(terra::extract(crop(tmax,e),sel,fun=mean,na.rm=TRUE,ID=FALSE)[1,])
  N[i,]<-as.numeric(terra::extract(crop(tmin,e),sel,fun=mean,na.rm=TRUE,ID=FALSE)[1,])}
saveRDS(list(val=val,P=P,TX=T,TN=N),"/tmp/ond_profiles.rds"); cat("extracted",nrow(val),"counties x 36 dekads\n")
