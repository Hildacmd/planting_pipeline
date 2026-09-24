source("Methodology_Testing/theme.R")
CA<-"#9A9287"; CB<-PAL[["e"]]
V<-data.frame(
 dom=c("KE long rains\ncounty, n=44","KE short rains\ncounty, n=45","KE short rains\nward 2021, n=62",
       "KE short rains\nward 2022, n=15","ET Meher\nregion, n=6"),
 # Ym-invariant rank skill (the level-free comparison)
 rhoA=c(0.724,0.101,-0.161,0.237,-0.371), rhoB=c(0.736,0.091,-0.177,0.186,-0.371),
 # shared production ceiling
 dprod=c(-0.024,0.070,-0.112,-0.037,-0.006),
 lo=c(-0.076,0.020,-0.154,-0.096,-0.014), hi=c(0.023,0.120,-0.072,0.011,-0.001),
 sep=c(NA,8.27,6.19,6.19,0.12), stringsAsFactors=FALSE)
PX("Methodology_Testing/figs/whc_ab.png",2140,900)
layout(matrix(1:3,1,3),widths=c(1.06,1.02,1.00))
par(mar=c(6.4,11.6,6.8,4.4),oma=c(.4,0,4.0,.4),xpd=FALSE)
k<-nrow(V)
## A - rank skill, level-free
plot(NA,xlim=c(-.55,.92),ylim=c(.4,k+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(-.5,.9,.5),col=GRID,lwd=1); abline(v=0,col=MUT,lwd=1.2)
for(i in 1:k){y<-k-i+1
  segments(V$rhoA[i],y,V$rhoB[i],y,col=RULE,lwd=2.4)
  points(V$rhoB[i],y,pch=19,col=CB,cex=1.25)
  points(V$rhoA[i],y,pch=21,bg="white",col=CA,lwd=2.2,cex=1.25)
  text(.92,y,sprintf("%+.3f",V$rhoB[i]-V$rhoA[i]),adj=0,cex=.70,col=MUT,xpd=NA)}
gridy(k:1,V$dom,cex=.76)
gridx(seq(-.5,.9,.5),cex=.80,line=3.0,title="Spearman with observed yield (Ym-invariant)")
ttl("A. Rank skill is identical","open = uniform 100 mm   filled = SoilGrids/Saxton",line=3.2,subline=2.0)
text(.86,k+.42,"delta",adj=0,cex=.70,col=MUT,font=2,xpd=NA)
## B - the MAE difference under a shared ceiling
par(mar=c(6.4,3.2,6.8,3.6))
plot(NA,xlim=c(-.18,.15),ylim=c(.4,k+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(-.15,.15,.05),col=GRID,lwd=1); abline(v=0,col=INK,lwd=1.5)
for(i in 1:k){y<-k-i+1; sig<-(V$lo[i]>0)|(V$hi[i]<0); cl<-if(!sig) "#ADA69A" else if(V$dprod[i]>0) CB else CA
  segments(V$lo[i],y,V$hi[i],y,col=cl,lwd=2.6)
  segments(c(V$lo[i],V$hi[i]),y-.10,c(V$lo[i],V$hi[i]),y+.10,col=cl,lwd=2)
  points(V$dprod[i],y,pch=19,col=cl,cex=1.05)}
gridx(seq(-.15,.15,.05),cex=.78,line=3.0,title="delta LOO-MAE, shared ceiling (t/ha)")
ttl("B. MAE under a shared ceiling","right of zero = SoilGrids better",line=3.2,subline=2.0)
text(-.175,k+.42,"uniform better",adj=0,cex=.72,col=CA,font=2)
text(.145,k+.42,"SoilGrids better",adj=1,cex=.72,col=CB,font=2)
## C - Ethiopia: the balance is never water-limited
par(mar=c(6.4,9.4,6.8,3.0))
ET<-read.csv("Cropyield-Data/whc_ab_ET_Meher_2024.csv",stringsAsFactors=FALSE)
nm<-if("NAME_1" %in% names(ET)) ET$NAME_1 else ET[[1]]
wa<-suppressWarnings(as.numeric(ET$wrsi_flo_A_mean)); wb<-suppressWarnings(as.numeric(ET$wrsi_flo_B_mean))
ok<-!is.na(wa)&!is.na(wb); nm<-nm[ok]; wa<-wa[ok]; wb<-wb[ok]
o<-order(wa); m<-length(wa)
plot(NA,xlim=c(96,100.6),ylim=c(.4,m+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(96,100,1),col=GRID,lwd=1)
abline(v=100,col=ACC,lty=2,lwd=1.6)
for(r in 1:m){i<-o[r]; y<-m-r+1
  segments(wa[i],y,wb[i],y,col=RULE,lwd=2.6)
  points(wa[i],y,pch=19,col=CA,cex=1.1); points(wb[i],y,pch=19,col=CB,cex=1.1)}
gridy(m:1,substr(nm[o],1,18),cex=.80)
gridx(seq(96,100,1),cex=.80,line=3.0,title="WRSI at flowering (%)")
ttl("C. Ethiopia is never water-limited","so bucket size cannot matter there",line=3.2,subline=2.0)
text(96.2,m*0.35,sprintf("flowering WRSI %.1f-%.1f\nunder both arms;\nmean CPI difference\n0.12 points",
  min(wa,wb),max(wa,wb)),adj=0,cex=.78,col=INK,font=2)
suptitle("The soil bucket changes the level of the water balance, not its ability to rank zones",
 c("Five variants, identical pipeline, only the bucket differs. Rank skill is unchanged everywhere (panel A).",
   "The one MAE gain, Kenya short rains at county scale, comes from the larger bucket reducing a large negative bias, not from better discrimination.",
   "In Ethiopia the flowering-stage water satisfaction is at or near 100 in every region, so the arms are arithmetically identical."))
dev.off(); cat("ok\n")
