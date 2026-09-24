source("Methodology_Testing/theme.R")
CV<-PAL[["e"]]; CD<-PAL[["two"]]
## S_veg swap (3.4.4): Spearman, NDVI/VCI vs DMP anomaly, per domain
SV<-data.frame(
 dom=c("Kenya long rains","Kenya short rains","Ethiopia Meher\n(admin-1)","Ethiopia Meher\n(admin-2)"),
 n=c(43,46,5,39), V=c(0.737,0.594,0.100,0.006), D=c(0.754,0.617,0.700,-0.033),
 lo=c(-0.0242,-0.0084,-0.0319,-0.0887), hi=c(0.0536,0.0312,0.1845,0.0225), stringsAsFactors=FALSE)
## DMP yield route (3.6)
DM<-data.frame(dom=c("KE long","KE short","KE ward 2021","KE ward 2022","ET Meher"),
 n=c(42,46,66,15,6), rho_d=c(0.76,0.72,0.18,0.52,0.60), rho_c=c(0.59,0.09,-0.18,0.19,-0.40),
 bias_d=c(-0.115,0.170,0.678,0.601,-0.396), over=c(0.9,1.1,3.9,10.3,0.8), stringsAsFactors=FALSE)
PX("Methodology_Testing/figs/index_tests.png",2120,900)
layout(matrix(1:3,1,3),widths=c(1.10,1.00,.98))
par(mar=c(6.4,10.6,6.6,2.6),oma=c(.4,0,3.8,.4),xpd=FALSE)
## A - swap makes no rank difference
k<-nrow(SV)
plot(NA,xlim=c(-.12,.92),ylim=c(.4,k+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(0,.9,.3),col=GRID,lwd=1); abline(v=0,col=MUT,lwd=1.2)
for(i in 1:k){y<-k-i+1
  segments(SV$V[i],y,SV$D[i],y,col=RULE,lwd=2.4)
  points(SV$V[i],y,pch=19,col=CV,cex=1.25); points(SV$D[i],y,pch=19,col=CD,cex=1.25)}
gridy(k:1,sprintf("%s\nn=%d",SV$dom,SV$n),cex=.76)
gridx(seq(0,.9,.3),cex=.80,line=3.0,title="Spearman rank correlation with observed yield")
ttl("A. Swapping the vegetation term",
    "blue = NDVI/VCI (shipped)   red = DMP productivity anomaly",line=3.0,subline=1.8)
text(.90,k+.42,"no significant difference\nin any season",adj=1,cex=.78,col=INK,font=2,xpd=NA)
## B - the paired CIs all straddle zero
par(mar=c(6.4,3.4,6.6,3.0))
plot(NA,xlim=c(-.12,.22),ylim=c(.4,k+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(-.1,.2,.1),col=GRID,lwd=1); abline(v=0,col=INK,lwd=1.5)
for(i in 1:k){y<-k-i+1; m<-(SV$lo[i]+SV$hi[i])/2
  segments(SV$lo[i],y,SV$hi[i],y,col=CD,lwd=2.6)
  segments(c(SV$lo[i],SV$hi[i]),y-.10,c(SV$lo[i],SV$hi[i]),y+.10,col=CD,lwd=2)
  points(m,y,pch=19,col=CD,cex=1.0)}
gridx(seq(-.1,.2,.1),cex=.80,line=3.0,title="paired-bootstrap difference in LOO MAE (t/ha)")
ttl("B. Every interval crosses zero","4 of 4 domains",line=3.0,subline=1.8)
text(0.21,k+.42,"the swap buys nothing",adj=1,cex=.78,col=INK,font=2)
## C - DMP ranks well but over-predicts
par(mar=c(6.4,8.6,6.6,4.2))
m<-nrow(DM)
plot(NA,xlim=c(-.55,.92),ylim=c(.4,m+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(-.5,.9,.5),col=GRID,lwd=1); abline(v=0,col=MUT,lwd=1.2)
for(i in 1:m){y<-m-i+1
  segments(DM$rho_c[i],y,DM$rho_d[i],y,col=RULE,lwd=2.4)
  points(DM$rho_c[i],y,pch=19,col="#9A9287",cex=1.15)
  points(DM$rho_d[i],y,pch=19,col=CD,cex=1.25)
  text(.94,y,sprintf("%.1fx",DM$over[i]),adj=0,cex=.74,col=INK,font=2,xpd=NA)}
gridy(m:1,sprintf("%s\nn=%d",DM$dom,DM$n),cex=.78)
gridx(seq(-.5,.9,.5),cex=.80,line=3.0,title="Spearman with observed yield")
ttl("C. The biomass route ranks well",
    "grey = CPI   red = DMP   right column = over-prediction",line=3.0,subline=1.8)
suptitle("An index reports canopy state; it cannot substitute for the prognostic or the causal instrument",
 c("Left: replacing NDVI/VCI with a DMP productivity anomaly inside the CPI changes rank skill in no season, and every paired interval crosses zero.",
   "Right: the biomass route out-ranks the CPI in all five domains, yet over-predicts yield by up to 10x at ward scale - it tracks outcome without attributing cause."))
dev.off(); cat("ok\n")
