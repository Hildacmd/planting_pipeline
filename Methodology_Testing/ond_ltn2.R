res<-readRDS("/tmp/ond_ltn.rds")
MON<-c("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
dlab<-function(d){d<-round(d); ifelse(is.na(d),"NA",sprintf("%s-d%d",MON[(d-1)%/%3+1],(d-1)%%3+1))}
res$pre_ratio<-res$r_augsep/(res$r_augsep+res$r_octnov)
# a "distinct OND season" = there is a real dry break before it.
res$break_type<-ifelse(res$r_augsep<100,"distinct OND (dry break)","continuous (no dry break)")
cat("=== CHIRPS-derived rainfall structure vs survey-derived OND regime ===\n")
print(table(survey=res$regime, chirps=res$break_type))
cat(sprintf("\nagreement (early~continuous, late~distinct): %d/%d\n",
  sum((res$regime=="early (Aug-Sep)")==(res$break_type=="continuous (no dry break)")),nrow(res)))
D<-res$break_type=="distinct OND (dry break)"
cat("\n=== Window check RESTRICTED to counties with a real dry break (n=",sum(D),") ===\n",sep="")
cat(sprintf("  CHIRPS onset inside new 28-33 : %d/%d (%.0f%%)\n",sum(res$chirps_onset[D]>=28&res$chirps_onset[D]<=33,na.rm=TRUE),sum(D),100*mean(res$chirps_onset[D]>=28&res$chirps_onset[D]<=33,na.rm=TRUE)))
cat(sprintf("  CHIRPS onset median           : %s   (range %s - %s)\n",dlab(median(res$chirps_onset[D])),dlab(min(res$chirps_onset[D])),dlab(max(res$chirps_onset[D]))))
cat(sprintf("  peak OND rain dekad median    : %s\n",dlab(median(res$pk_ond[D]))))
cat(sprintf("  survey onset median           : %s\n",dlab(median(res$onset_survey[D]))))
cat("\n  Counties whose CHIRPS onset falls OUTSIDE 28-33 despite a dry break:\n")
for(i in which(D & (res$chirps_onset<28|res$chirps_onset>33))) cat(sprintf("    %-14s CHIRPS %s  survey %s  AugSep %.0fmm\n",res$county[i],dlab(res$chirps_onset[i]),dlab(res$onset_survey[i]),res$r_augsep[i]))
cat("\n=== The three flagged-doubtful assignments, adjudicated by CHIRPS ===\n")
for(cn in c("Garissa","Bomet","Kisii")){i<-which(res$county==cn)
 cat(sprintf("  %-9s survey=%-14s CHIRPS AugSep %5.0fmm OctNov %3.0fmm onset %s -> climatology says %s\n",
   cn,res$regime[i],res$r_augsep[i],res$r_octnov[i],dlab(res$chirps_onset[i]),
   ifelse(res$break_type[i]=="continuous (no dry break)","EARLY/continuous","LATE/distinct")))}
cat("\n=== Non-parametric separation on the CHIRPS structure variable ===\n")
w<-wilcox.test(res$r_augsep[res$regime=="early (Aug-Sep)"],res$r_augsep[res$regime!="early (Aug-Sep)"])
a<-res$r_augsep[res$regime=="early (Aug-Sep)"];b<-res$r_augsep[res$regime!="early (Aug-Sep)"]
auc<-mean(outer(a,b,">")+0.5*outer(a,b,"=="))
cat(sprintf("  Aug-Sep rain, early vs late: AUC=%.3f  Wilcoxon p=%.4f  (AUC 0.5 = no separation)\n",auc,w$p.value))
saveRDS(res,"/tmp/ond_ltn.rds")
