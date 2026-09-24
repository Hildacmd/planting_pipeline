source("Methodology_Testing/theme.R")
F<-data.frame(
 fr=c("KE long rains\ncounty, n=42","KE short rains\ncounty, n=46","Kitui ward 2021\ncrop cuts, n=66",
      "Kitui ward 2022\ncrop cuts, n=15","ET Meher\nregion, n=6"),
 rho_cpi=c(0.59,0.09,-0.18,0.19,-0.40),
 rho_dmp_pre=c(0.72,0.63,0.39,0.36,0.60), rho_dmp_cyc=c(0.76,0.72,0.18,0.52,0.60),
 hi_pre=c(0.272,0.290,0.071,0.021,0.482), hi_cyc=c(0.417,0.337,0.095,0.043,0.482),
 ov_pre=c(1.7,1.5,6.7,21.7,0.8), ov_cyc=c(0.9,1.1,3.9,10.3,0.8), stringsAsFactors=FALSE)
CC<-"#9A9287"; CD<-PAL[["two"]]; CP<-"#E0B48A"
PX("Methodology_Testing/figs/dmp_route.png",2160,930)
layout(matrix(1:3,1,3),widths=c(1.10,1.00,.98))
par(mar=c(6.4,11.4,7.0,4.0),oma=c(.4,0,4.4,.4),xpd=FALSE)
k<-nrow(F)
## A - rank skill
plot(NA,xlim=c(-.55,.92),ylim=c(.4,k+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(-.5,.9,.5),col=GRID,lwd=1); abline(v=0,col=MUT,lwd=1.2)
for(i in 1:k){y<-k-i+1
  segments(F$rho_cpi[i],y,F$rho_dmp_cyc[i],y,col=RULE,lwd=2.4)
  points(F$rho_dmp_pre[i],y,pch=21,bg="white",col=CP,lwd=2,cex=1.0)
  points(F$rho_cpi[i],y,pch=19,col=CC,cex=1.2)
  points(F$rho_dmp_cyc[i],y,pch=19,col=CD,cex=1.3)}
gridy(k:1,F$fr,cex=.76)
gridx(seq(-.5,.9,.5),cex=.80,line=3.0,title="Spearman with observed yield")
ttl("A. Ranks better in every frame",
    "grey = CPI   red = DMP now   open = DMP before the cycle fix",line=3.4,subline=2.0)
text(-.53,1.55,"CPI ranks\nbackwards here",adj=0,cex=.72,col=CC,font=2)
## B - implied harvest index
par(mar=c(6.4,3.2,7.0,3.4))
plot(NA,xlim=c(0,.62),ylim=c(.4,k+.6),axes=FALSE,xlab="",ylab="")
rect(.30,.4,.55,k+.6,col="#EAF0E8",border=NA)
abline(v=seq(0,.6,.2),col=GRID,lwd=1)
for(i in 1:k){y<-k-i+1
  segments(F$hi_pre[i],y,F$hi_cyc[i],y,col=RULE,lwd=2.2)
  points(F$hi_pre[i],y,pch=21,bg="white",col=CP,lwd=2,cex=1.0)
  points(F$hi_cyc[i],y,pch=19,col=CD,cex=1.3)}
abline(v=.45,col=ACC,lty=2,lwd=1.5)
gridx(seq(0,.6,.2),cex=.80,line=3.0,title="harvest index implied by the observations")
ttl("B. The level is biomass-limited","band = agronomic range 0.30-0.55",line=3.4,subline=2.0)
text(.44,k+.42,"HI assumed 0.45",adj=1,cex=.70,col=ACC,font=2)
## C - over-prediction, log scale
par(mar=c(6.4,3.2,7.0,4.6))
plot(NA,xlim=log10(c(.6,46)),ylim=c(.4,k+.6),axes=FALSE,xlab="",ylab="")
tk<-c(1,2,5,10,20); abline(v=log10(tk),col=GRID,lwd=1); abline(v=0,col=INK,lwd=1.5)
for(i in 1:k){y<-k-i+1
  segments(log10(F$ov_cyc[i]),y,log10(F$ov_pre[i]),y,col=RULE,lwd=2.2)
  points(log10(F$ov_pre[i]),y,pch=21,bg="white",col=CP,lwd=2,cex=1.0)
  points(log10(F$ov_cyc[i]),y,pch=19,col=CD,cex=1.3)
  text(log10(45),y,sprintf("%.1fx",F$ov_cyc[i]),adj=1,cex=.76,col=CD,font=2)}
gridx(log10(tk),paste0(tk,"x"),cex=.80,line=3.0,title="yield over-prediction factor (log scale)")
ttl("C. Mixed pixels break the level","1x = correct level",line=3.4,subline=2.0)
suptitle("The biomass route ranks outcomes well and states their level badly",
 c("MODIS MOD17A2HGF GPP stands in for Copernicus DMP, converted by the Monteith chain (CUE 0.45, above-ground 0.80, HI 0.45).",
   "Open circles are the run quoted in the current text; filled circles are the same test after the per-pixel crop cycle replaced the fixed one.",
   "The cycle fix moves every number in the biomass route's favour, but the crop-cut wards remain irreconcilable: implied HI 0.04-0.10 against an agronomic 0.30-0.55."))
dev.off(); cat("ok\n")
