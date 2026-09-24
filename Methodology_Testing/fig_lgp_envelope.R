source("Methodology_Testing/theme.R")
CY<-"Cropyield-Data"
DOM<-list(list("Kenya long rains","lgp_stages_ke_long_2024.csv",44),
          list("Kenya short rains","lgp_stages_ke_short_2024.csv",46),
          list("Ethiopia Meher","lgp_stages_et_meher_2024.csv",6))
wm<-function(d,b){v<-suppressWarnings(as.numeric(d[[paste0(b,"_mean")]]))
  n<-suppressWarnings(as.numeric(d[[paste0(b,"_count")]])); k<-!is.na(v)&!is.na(n)&n>0
  sum(v[k]*n[k])/sum(n[k])}
S<-lapply(DOM,function(x){d<-read.csv(file.path(CY,x[[2]]),stringsAsFactors=FALSE)
  list(nm=x[[1]],n=x[[3]],lgp=wm(d,"lgp_clim_d"),
       veg=wm(d,"veg_gdd_d"),flo=wm(d,"flo_gdd_d"),grf=wm(d,"grf_gdd_d"),cyc=wm(d,"cycle_gdd_d"),
       vegF=wm(d,"veg_fixed_d"),floF=wm(d,"flo_fixed_d"),grfF=wm(d,"grf_fixed_d"),
       floin=wm(d,"flo_inside_lgp"),grfin=wm(d,"grf_inside_lgp"),
       flo_sd=sd(suppressWarnings(as.numeric(d$flo_gdd_d_mean)),na.rm=TRUE))})

PX("Methodology_Testing/figs/lgp_envelope_vs_clock.png",2020,1060)
layout(matrix(c(1,2,3,4,4,4),2,3,byrow=TRUE),heights=c(1.10,.90))
par(mar=c(4.6,3.2,6.8,2.2),oma=c(1.0,2.2,6.4,1.0),xpd=FALSE)
C_L<-"#9C8FA8"; C_G<-PAL[["one"]]; C_F<-"#9A9287"
for(s in S){
  XM<-max(s$lgp,s$cyc,s$grfF)*1.10
  plot(NA,xlim=c(0,XM),ylim=c(.2,2.9),axes=FALSE,xlab="",ylab="")
  abline(v=pretty(c(0,XM),5),col=GRID,lwd=1)
  # row 2: the climatic LGP envelope - deliberately featureless
  rect(0,2.1,s$lgp,2.62,col=paste0(C_L,"55"),border=C_L,lwd=1.8)
  text(s$lgp/2,2.36,"no interior structure",cex=.74,col="#6F6478",font=3)
  text(s$lgp+3,2.36,sprintf("%.0f d",s$lgp),adj=0,cex=.74,col=C_L,font=2)
  # row 1: the GDD clock, with the three stages resolved
  rect(0,1.16,s$cyc,1.68,col=paste0(C_G,"22"),border=C_G,lwd=1.8)
  for(j in 1:3){ x<-c(s$veg,s$flo,s$grf)[j]
    segments(x,1.12,x,1.72,col=C_G,lwd=2.6)
    points(x,1.42,pch=19,col=C_G,cex=.9)}
  text(s$cyc+3,1.42,sprintf("%.0f d",s$cyc),adj=0,cex=.74,col=C_G,font=2)
  text(s$veg,0.92,"adv.\nveg",cex=.62,col=C_G,adj=.5)
  text(s$flo,0.92,"flower",cex=.62,col=C_G,adj=.5)
  text(s$grf,0.92,"grain\nfill",cex=.62,col=C_G,adj=.5)
  # row 0: what the fixed Kc curve assumes, for reference
  for(j in 1:3){x<-c(s$vegF,s$floF,s$grfF)[j]; segments(x,0.38,x,0.62,col=C_F,lwd=2.2)}
  text(-2,0.50,"fixed Kc",adj=1,cex=.66,col=C_F,xpd=NA)
  text(-2,1.42,"GDD clock",adj=1,cex=.72,col=C_G,font=2,xpd=NA)
  text(-2,2.36,"climatic LGP",adj=1,cex=.72,col=C_L,font=2,xpd=NA)
  gridx(pretty(c(0,XM),5),cex=.72,line=2.4,title="days after planting")
  mtext(sprintf("%s   (n=%d)",s$nm,s$n),3,line=2.6,adj=0,cex=.92,font=2,col=INK)
  mtext("LGP: 0 of 3 stages       clock: 3 of 3",3,line=1.4,adj=0,cex=.74,col=INK,font=2)
  mtext(sprintf("flowering %.0f%% / grain fill %.0f%% inside the LGP",100*s$floin,100*s$grfin),
    3,line=0.3,adj=0,cex=.68,col=MUT)}

## bottom strip - the clock also resolves BETWEEN counties; the LGP envelope does not constrain that
par(mar=c(5.0,12.4,5.0,3.0))
d<-read.csv(file.path(CY,"lgp_stages_ke_long_2024.csv"),stringsAsFactors=FALSE)
fl<-suppressWarnings(as.numeric(d$flo_gdd_d_mean)); fl<-fl[!is.na(fl)]
lg<-suppressWarnings(as.numeric(d$lgp_clim_d_mean)); lg<-lg[!is.na(lg)]
plot(NA,xlim=c(0,max(fl,lg)*1.04),ylim=c(.4,2.6),axes=FALSE,xlab="",ylab="")
abline(v=pretty(c(0,max(fl,lg)),6),col=GRID,lwd=1)
for(r in list(list(lg,2,C_L,"climatic LGP length"),list(fl,1,C_G,"GDD flowering date"))){
  v<-r[[1]]; y<-r[[2]]; cl<-r[[3]]
  q<-quantile(v,c(.25,.5,.75))
  rect(q[1],y-.20,q[3],y+.20,col=paste0(cl,"2A"),border=cl,lwd=2)
  segments(q[2],y-.20,q[2],y+.20,col=cl,lwd=3.4)
  points(v,jitter(rep(y,length(v)),amount=.11),pch=19,col=paste0(cl,"88"),cex=.75)}
segments(85,0.55,85,1.75,col=C_F,lty=2,lwd=1.8)
text(87,0.62,"the fixed Kc curve puts flowering here, for every county",adj=0,cex=.74,col=C_F,font=2)
gridy(2:1,c("climatic LGP length","GDD flowering date"),cex=.84)
gridx(pretty(c(0,max(fl,lg)),6),cex=.78,line=2.8,title="days")
mtext("Kenya long rains, per county: the clock varies where the envelope cannot",3,line=1.6,adj=0,cex=.92,font=2,col=INK)
mtext("Each dot is one county. The LGP tells you how long the season is; it never tells you when flowering happens inside it.",
  3,line=0.4,adj=0,cex=.70,col=MUT)
suptitle("The LGP is an envelope: it bounds the season but has no interior structure",
 c("The climatic LGP (FAO P/PET >= 0.5) returns a single start-to-end interval. Nothing in that definition marks advanced vegetative, flowering or grain filling.",
   "The GDD clock places all three, and places them differently in every county. This is why LGP screens WHERE a crop can grow but cannot time stages WITHIN a season."),cex=1.20)
dev.off(); cat("ok\n")
