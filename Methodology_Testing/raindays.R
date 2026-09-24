suppressPackageStartupMessages(library(terra))
DIR<-"/Users/hildamanzi/ICPAC-WORK/CHIRPS DATA/chirps_v3_africa_daily"
KEN<-"/Users/hildamanzi/AEZ-COUNTRIES/gadm41_KEN_shp/gadm41_KEN_1.shp"
norm<-function(x) tolower(gsub("[^A-Za-z]","",x))
val<-read.csv("Cropyield-Data/ond_window_ltn_validation.csv",stringsAsFactors=FALSE); val$k<-norm(val$county)
v<-vect(KEN); v$k<-norm(v$NAME_1); v<-v[v$k %in% val$k,]
v<-v[match(val$k,v$k),]                       # align polygon order to the validation table
YRS<-1996:2025; MOS<-7:12; THR<-c(1,10)
# accumulators: county x dekad(19-36) x threshold
ACC<-array(0,dim=c(nrow(val),18,length(THR))); NY<-0
E<-ext(33.8,42.1,-4.9,5.2)
for(y in YRS){
  ok<-TRUE
  for(mo in MOS){
    f<-sprintf("%s/chirps-v3.0.rnl.africa.%d.%02d.days_p05.nc",DIR,y,mo)
    if(!file.exists(f)){ok<-FALSE;next}
    r<-crop(rast(f),E); nd<-nlyr(r)
    grp<-pmin((seq_len(nd)-1)%/%10+1,3)        # d1=1-10, d2=11-20, d3=21-end
    for(ti in seq_along(THR)){
      wet<-r>=THR[ti]
      for(dd in 1:3){
        cnt<-sum(wet[[which(grp==dd)]])
        x<-terra::extract(cnt,v,fun=mean,na.rm=TRUE,ID=FALSE)[,1]
        col<-(mo-7)*3+dd                        # 1..18  -> dekads 19..36
        ACC[,col,ti]<-ACC[,col,ti]+ifelse(is.na(x),0,x)
      }}}
  if(ok) NY<-NY+1
  cat(y," ")
}
cat("\nyears used:",NY,"\n")
RD<-ACC/NY
saveRDS(list(county=val$county,survey=val$survey_ond_regime,chirps=val$chirps_rain_structure,
             rd1=RD[,,1],rd10=RD[,,2],dekads=19:36),"/tmp/raindays.rds")
cat("mean rain days (>=1mm) per dekad, dk19-36:\n")
cat(round(colMeans(RD[,,1]),1),"\n")
