suppressPackageStartupMessages(library(terra))
CH<-"/Users/hildamanzi/ICPAC-WORK/CHIRPS DATA/chirps_v3_ltn/chirps-v3.0.ltn.dekadal.1996-2025.gha_p05.tif"
CTD<-"/Users/hildamanzi/ICPAC-WORK/DOWNLOADED RASTER DATASETS/chirts_ltn"
KEN<-"/Users/hildamanzi/AEZ-COUNTRIES/gadm41_KEN_shp/gadm41_KEN_1.shp"
MON<-c("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
dlab<-function(d){d<-round(d); ifelse(is.na(d),"NA",sprintf("%s-d%d",MON[(d-1)%/%3+1],(d-1)%%3+1))}
norm<-function(x) tolower(gsub("[^A-Za-z]","",x))

reg<-read.csv("Cropyield-Data/ond_regimes.csv",stringsAsFactors=FALSE)
reg$k<-norm(reg$county)
v<-vect(KEN); v$k<-norm(v$NAME_1)

rain<-rast(CH)
tmax<-rast(file.path(CTD,"chirts.ltn.dekadal.tmax.1996-2025.gha_p05.tif"))
tmin<-rast(file.path(CTD,"chirts.ltn.dekadal.tmin.1996-2025.gha_p05.tif"))

res<-do.call(rbind,lapply(seq_len(nrow(reg)),function(i){
  sel<-v[v$k==reg$k[i],]
  if(nrow(sel)==0) return(NULL)
  e<-ext(sel)+0.25
  pr<-as.numeric(terra::extract(crop(rain,e),sel,fun=mean,na.rm=TRUE,ID=FALSE)[1,])
  tx<-as.numeric(terra::extract(crop(tmax,e),sel,fun=mean,na.rm=TRUE,ID=FALSE)[1,])
  tn<-as.numeric(terra::extract(crop(tmin,e),sel,fun=mean,na.rm=TRUE,ID=FALSE)[1,])
  # FEWS/FAO 25-20mm onset rule scanned across the whole Jul-Dec half year (dk 19-34)
  ons<-NA_real_
  for(d in 19:34) if(pr[d]>25 && sum(pr[(d+1):min(d+2,36)],na.rm=TRUE)>20){ons<-d;break}
  tm<-(tx+tn)/2; gdd<-pmax(pmin(tm,30)-10,0)*10.14
  data.frame(county=reg$county[i], regime=reg$ond_regime[i], onset_survey=reg$onset_dk[i],
    n_survey=reg$n_survey[i],
    chirps_onset=ons,
    r_augsep=sum(pr[22:27]), r_octnov=sum(pr[28:33]), r_julsep=sum(pr[19:27]),
    pk_ond=(27+which.max(pr[28:34])),
    tmax_ond=mean(tx[28:33]), tmean_ond=mean(tm[28:33]), gdd_ond=sum(gdd[28:33]),
    tmax_augsep=mean(tx[22:27]),
    p_prof=I(list(pr[19:36])), stringsAsFactors=FALSE)
}))
saveRDS(res,"/tmp/ond_ltn.rds")
res$pre_ratio<-res$r_augsep/(res$r_augsep+res$r_octnov)
E<-res$regime=="early (Aug-Sep)"; L<-!E

cat("=== CHIRPS LTN 1996-2025, per county ===\n")
cat(sprintf("%-14s %-14s %8s %9s %8s %8s %7s %7s\n","county","regime","survey","CHIRPSons","AugSep","OctNov","pre%","TmaxOND"))
o<-order(res$regime,res$onset_survey)
for(i in o) cat(sprintf("%-14s %-14s %8s %9s %8.0f %8.0f %6.0f%% %7.1f\n",
  substr(res$county[i],1,13), substr(res$regime[i],1,13), dlab(res$onset_survey[i]),
  dlab(res$chirps_onset[i]), res$r_augsep[i], res$r_octnov[i], 100*res$pre_ratio[i], res$tmax_ond[i]))

cat("\n=== Does CHIRPS climatology separate the two survey regimes? ===\n")
tst<-function(nm,x){w<-suppressWarnings(wilcox.test(x[E],x[L]));
  cat(sprintf("  %-22s early %8.1f   late %8.1f   Wilcoxon p=%.4f %s\n",nm,median(x[E],na.rm=TRUE),
      median(x[L],na.rm=TRUE),w$p.value,ifelse(w$p.value<0.05,"** SEPARATES","   ns")))}
tst("Aug-Sep rain (mm)",res$r_augsep); tst("Jul-Sep rain (mm)",res$r_julsep)
tst("Oct-Nov rain (mm)",res$r_octnov); tst("pre-season fraction",res$pre_ratio)
tst("CHIRPS onset dekad",res$chirps_onset); tst("Tmax OND (C)",res$tmax_ond)
tst("Tmax Aug-Sep (C)",res$tmax_augsep); tst("GDD OND",res$gdd_ond)

cat("\n=== Is the shipped window dk 28-33 consistent with CHIRPS onset? ===\n")
ok<-res$chirps_onset>=28 & res$chirps_onset<=33
cat(sprintf("  CHIRPS onset inside 28-33 : %d/%d (%.0f%%)\n",sum(ok,na.rm=TRUE),sum(!is.na(res$chirps_onset)),
    100*mean(ok,na.rm=TRUE)))
cat(sprintf("  old window 28-34          : %d/%d\n",sum(res$chirps_onset>=28&res$chirps_onset<=34,na.rm=TRUE),sum(!is.na(res$chirps_onset))))
cat(sprintf("  CHIRPS onset range        : %s to %s (median %s)\n",dlab(min(res$chirps_onset,na.rm=TRUE)),
    dlab(max(res$chirps_onset,na.rm=TRUE)),dlab(median(res$chirps_onset,na.rm=TRUE))))
cat(sprintf("  survey onset median       : early %s   late %s\n",dlab(median(res$onset_survey[E])),dlab(median(res$onset_survey[L]))))
cat(sprintf("  survey-minus-CHIRPS lead  : early %.1f dk   late %.1f dk\n",
    median(res$chirps_onset[E]-res$onset_survey[E],na.rm=TRUE),
    median(res$chirps_onset[L]-res$onset_survey[L],na.rm=TRUE)))
cat(sprintf("  peak OND rain dekad       : early %s   late %s\n",dlab(median(res$pk_ond[E])),dlab(median(res$pk_ond[L]))))
cat(sprintf("\n  Spearman survey-onset vs CHIRPS-onset  rho=%.3f (p=%.3f)\n",
   cor(res$onset_survey,res$chirps_onset,method="spearman",use="complete.obs"),
   suppressWarnings(cor.test(res$onset_survey,res$chirps_onset,method="spearman"))$p.value))
cat(sprintf("  Spearman survey-onset vs Aug-Sep rain  rho=%.3f (p=%.3f)\n",
   cor(res$onset_survey,res$r_augsep,method="spearman",use="complete.obs"),
   suppressWarnings(cor.test(res$onset_survey,res$r_augsep,method="spearman"))$p.value))
