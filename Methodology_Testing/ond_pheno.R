res<-readRDS("/tmp/ond_ltn.rds")
MON<-c("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
dlab<-function(d){d<-round(d);ifelse(is.na(d),"NA",sprintf("%s-d%d",MON[(d-1)%/%3+1],(d-1)%%3+1))}
norm<-function(x) tolower(gsub("[^A-Za-z]","",x))
ph<-read.csv("Cropyield-Data/modis_pheno_ond_ke.csv",stringsAsFactors=FALSE)
# GAUL districts -> counties via the crosswalk already in the repo
cw<-system("python3 -c \"import sys;sys.path.insert(0,'src');from kenya_gaul_counties import DISTRICT_TO_COUNTY;[print(k+'|'+v) for k,v in DISTRICT_TO_COUNTY.items()]\"",intern=TRUE)
map<-setNames(sub(".*\\|","",cw),norm(sub("\\|.*","",cw)))
ph$county<-map[norm(ph$ADM2_NAME)]
ph<-ph[!is.na(ph$county) & !is.na(ph$g2),]
agg<-aggregate(cbind(g1,g2,n_cycle2,n_years)~county,ph,median)
agg$k<-norm(agg$county); res$k<-norm(res$county)
m<-merge(res,agg[,c("k","g1","g2","n_cycle2","n_years")],by="k")
m$frac2<-m$n_cycle2/m$n_years
E<-m$regime=="early (Aug-Sep)"
cat(sprintf("matched %d/%d counties to MODIS MCD12Q2 cropland green-up\n\n",nrow(m),nrow(res)))
cat(sprintf("%-14s %-14s %9s %9s %9s %8s\n","county","regime","survey","MODIS g2","CHIRPSons","2nd-cyc"))
for(i in order(m$regime,m$g2)) cat(sprintf("%-14s %-14s %9s %9s %9s %7.0f%%\n",
  substr(m$county[i],1,13),substr(m$regime[i],1,13),dlab(m$onset_survey[i]),dlab(m$g2[i]),
  dlab(m$chirps_onset[i]),100*m$frac2[i]))
cat("\n=== MODIS second-cycle green-up vs the detection window ===\n")
ok<-m$g2>=28 & m$g2<=33
cat(sprintf("  green-up dk median %s  range %s - %s\n",dlab(median(m$g2)),dlab(min(m$g2)),dlab(max(m$g2))))
cat(sprintf("  green-up inside 28-33 : %d/%d (%.0f%%)\n",sum(ok),nrow(m),100*mean(ok)))
D<-m$r_augsep<100
cat(sprintf("  ...restricted to dry-break counties: %d/%d (%.0f%%)\n",sum(ok&D),sum(D),100*mean(ok[D])))
cat(sprintf("  green-up LAGS survey onset by median %.1f dekads (~%.0f days)\n",median(m$g2-m$onset_survey),10.14*median(m$g2-m$onset_survey)))
cat(sprintf("  green-up LAGS CHIRPS onset by median %.1f dekads (~%.0f days)\n",median(m$g2-m$chirps_onset,na.rm=TRUE),10.14*median(m$g2-m$chirps_onset,na.rm=TRUE)))
for(nm in c("g2","frac2")){x<-m[[nm]];w<-suppressWarnings(wilcox.test(x[E],x[!E]))
 cat(sprintf("  %-22s early %7.2f  late %7.2f   p=%.4f %s\n",
   ifelse(nm=="g2","MODIS green-up dekad","2nd-cycle detect rate"),median(x[E]),median(x[!E]),w$p.value,
   ifelse(w$p.value<0.05,"** SEPARATES","   ns")))}
cat(sprintf("\n  Spearman MODIS g2 vs survey onset  rho=%+.3f (p=%.3f)\n",
  cor(m$g2,m$onset_survey,method="spearman"),suppressWarnings(cor.test(m$g2,m$onset_survey,method="spearman"))$p.value))
cat(sprintf("  Spearman MODIS g2 vs CHIRPS onset  rho=%+.3f (p=%.3f)\n",
  cor(m$g2,m$chirps_onset,method="spearman",use="complete.obs"),suppressWarnings(cor.test(m$g2,m$chirps_onset,method="spearman"))$p.value))
saveRDS(m,"/tmp/ond_pheno.rds")
