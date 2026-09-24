source("Methodology_Testing/theme.R")
m<-read.csv("Cropyield-Data/whc_native_vwc_vs_saxton.csv",stringsAsFactors=FALSE)
CS<-PAL[["e"]]; CV<-PAL[["two"]]
PX("Methodology_Testing/figs/whc_native_vwc.png",2000,1320)
layout(matrix(1:4,2,2,byrow=TRUE))
par(mar=c(6.0,6.6,6.4,3.0),oma=c(.6,0,6.6,.6),xpd=FALSE)
## A - distributions
xr<-range(c(m$vwc100,m$whc_R10))*c(.92,1.06)
bS<-density(m$whc_R10); bV<-density(m$vwc100)
yl<-c(0,max(bS$y,bV$y)*1.24)
plot(NA,xlim=xr,ylim=yl,axes=FALSE,xlab="",ylab="")
abline(v=pretty(xr,5),col=GRID,lwd=1)
polygon(bS$x,bS$y,col=paste0(CS,"33"),border=CS,lwd=2.4)
polygon(bV$x,bV$y,col=paste0(CV,"33"),border=CV,lwd=2.4)
abline(v=c(median(m$whc_R10),median(m$vwc100)),col=c(CS,CV),lty=2,lwd=1.8)
gridx(pretty(xr,5),cex=.80,line=3.2,title="WHC (mm) at the shipped 1.0 m rooting depth")
gridy(pretty(yl,4),rep("",length(pretty(yl,4))),cex=.80,line=2.4,title="density of counties")
ttl("A. The two routes agree on level","median 123.6 vs 106.1 mm - a 15% offset",line=3.4,subline=2.0)
text(median(m$whc_R10),yl[2]*.97,"Saxton-Rawls",col=CS,cex=.80,font=2,adj=.5)
text(median(m$vwc100),yl[2]*.86,"native VWC",col=CV,cex=.80,font=2,adj=.5)
## B - but not on pattern
par(mar=c(6.4,6.4,7.0,2.8))
plot(NA,xlim=range(m$whc_R10)*c(.96,1.04),ylim=range(m$vwc100)*c(.94,1.06),axes=FALSE,xlab="",ylab="")
abline(h=pretty(range(m$vwc100),5),v=pretty(range(m$whc_R10),5),col=GRID,lwd=1)
lim<-range(c(m$whc_R10,m$vwc100)); segments(lim[1],lim[1],lim[2],lim[2],col=MUT,lty=3,lwd=1.4)
points(m$whc_R10,m$vwc100,pch=19,col=paste0(CV,"AA"),cex=1.25)
gridx(pretty(range(m$whc_R10),5),cex=.80,line=3.2,title="Saxton-Rawls WHC (mm)")
gridy(pretty(range(m$vwc100),5),cex=.80,line=3.4,title="native VWC WHC (mm)")
ttl("B. But not on pattern","which county holds more water",line=3.4,subline=2.0)
text(min(m$whc_R10)*.985,min(m$vwc100)*1.02,
  sprintf("r = %+.2f   rho = %+.2f",cor(m$whc_R10,m$vwc100),cor(m$whc_R10,m$vwc100,method="spearman")),
  adj=0,cex=.86,col=INK,font=2)
text(max(m$whc_R10)*.995,max(m$vwc100)*1.04,"dotted = 1:1",adj=1,cex=.72,col=MUT)
## C - spread
par(mar=c(6.0,9.8,6.4,3.4))
o<-order(m$vwc100); n<-nrow(m)
xr3<-range(c(m$vwc100,m$whc_R10))*c(.94,1.05)
plot(NA,xlim=xr3,ylim=c(.4,n+.6),axes=FALSE,xlab="",ylab="")
abline(v=pretty(xr3,6),col=GRID,lwd=1)
for(r in 1:n){i<-o[r]; y<-n-r+1
  segments(m$vwc100[i],y,m$whc_R10[i],y,col=RULE,lwd=1.8)
  points(m$whc_R10[i],y,pch=19,col=CS,cex=.72); points(m$vwc100[i],y,pch=19,col=CV,cex=.72)}
gridy(seq(n,1,by=-6),m$county[o][seq(1,n,by=6)],cex=.68)
gridx(pretty(xr3,6),cex=.80,line=3.2,title="WHC (mm)")
ttl("C. 2.2x the spatial spread",sprintf("Saxton %.0f-%.0f mm (blue)   native VWC %.0f-%.0f mm (red)",
    min(m$whc_R10),max(m$whc_R10),min(m$vwc100),max(m$vwc100)),line=3.4,subline=2.0)

## D - and the pipeline outcome
par(mar=c(6.0,10.6,6.4,4.6))
R<-data.frame(arm=c("uniform 100 mm","Saxton-Rawls","native VWC"),
  whc=c(100,123,105), cpi=c(52.5,59.5,54.3), mae=c(0.527,0.516,0.524),
  bias=c(-0.080,0.067,-0.042), rho=c(0.601,0.596,0.591), stringsAsFactors=FALSE)
CO2<-c("#9A9287",CS,CV)
plot(NA,xlim=c(0,.80),ylim=c(.4,3.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(0,.8,.2),col=GRID,lwd=1)
for(i in 1:3){y<-4-i
  rect(0,y-.24,R$rho[i],y+.24,col=paste0(CO2[i],"38"),border=NA)
  segments(0,y,R$rho[i],y,col=CO2[i],lwd=4,lend=1)
  text(R$rho[i]+.016,y,sprintf("%.3f",R$rho[i]),adj=0,cex=.80,col=CO2[i],font=2)
  text(.82,y,sprintf("MAE %.3f",R$mae[i]),adj=0,cex=.74,col=CO2[i],font=2,xpd=NA)}
gridy(3:1,R$arm,cex=.84)
gridx(seq(0,.8,.2),cex=.80,line=3.0,title="Spearman with observed yield")
ttl("D. No difference at all","every pairwise interval crosses zero",line=3.4,subline=2.0)

suptitle("SoilGrids' own water-content layers give a similar bucket in the mean and a different one in the pattern",
 c("wv0033 (field capacity) minus wv1500 (wilting point), integrated to the shipped 1.0 m, fetched from ISRIC's WCS - these layers are not hosted in Earth Engine.",
   "The level offset is small and sits inside the 74-147 mm envelope the rooting-depth test already covered. The spatial disagreement does not: r = +0.12 across 45 counties.",
   "That is why this extension needed its own pipeline run rather than an appeal to the depth sensitivity, which perturbed the level and never the pattern.",
   "Run through the balance at the shipped depth, no pair differs: Spearman 0.591 / 0.596 / 0.601 and MAE within 0.011 t/ha, with every bootstrap interval crossing zero."),cex=1.16)
dev.off(); cat("ok\n")
