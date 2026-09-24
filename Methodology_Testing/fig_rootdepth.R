source("Methodology_Testing/theme.R")
D<-data.frame(arm=c("uniform\n100 mm","SoilGrids\n0.6 m","SoilGrids\n1.0 m","SoilGrids\n1.2 m"),
  whc=c(100,73.9,122.7,147.2), wrsi=c(83.3,77.1,86.5,89.3), cpi=c(52.5,43.2,59.3,65.6),
  mae=c(0.527,0.593,0.517,0.536), bias=c(-0.080,-0.275,0.064,0.196),
  rho=c(0.601,0.582,0.591,0.563), stringsAsFactors=FALSE)
CU<-"#9A9287"; CS<-PAL[["e"]]; SHIP<-3
CO<-c(CU,CS,CS,CS); LW<-c(2,2,3.6,2)
PX("Methodology_Testing/figs/whc_rootdepth.png",2140,900)
layout(matrix(1:3,1,3),widths=c(1.06,1.00,1.00))
par(mar=c(6.6,6.4,7.0,2.6),oma=c(.4,0,4.2,.4),xpd=FALSE)
bars<-function(v,ylab,ttl_,sub,fmt="%.0f",ref=NULL,refl=NULL,ylim=NULL){
  yl<-if(is.null(ylim)) c(0,max(v)*1.22) else ylim
  plot(NA,xlim=c(.4,4.6),ylim=yl,axes=FALSE,xlab="",ylab="")
  abline(h=pretty(yl,5),col=GRID,lwd=1)
  if(!is.null(ref)){abline(h=ref,col=ACC,lty=2,lwd=1.5)
    text(4.55,ref+diff(yl)*.035,refl,adj=1,cex=.72,col=ACC,font=2)}
  for(i in 1:4){rect(i-.32,min(0,yl[1]),i+.32,v[i],col=paste0(CO[i],"55"),border=CO[i],lwd=LW[i])
    text(i,v[i]+diff(yl)*.045*sign(ifelse(v[i]>=0,1,-1)),sprintf(fmt,v[i]),cex=.82,col=CO[i],font=2)}
  rect(SHIP-.40,yl[1],SHIP+.40,yl[2],col=NA,border=CS,lwd=1,lty=3)
  axis(1,at=1:4,labels=D$arm,col=GRID,col.axis=MUT,cex.axis=.80,tck=-.018,padj=.5)
  gridy(pretty(yl,5),cex=.80,line=3.6,title=ylab)
  ttl(ttl_,sub,line=3.4,subline=2.0)}
bars(D$whc,"mm","A. The lever works","rooting depth doubles the bucket")
bars(D$cpi,"CPI points","B. And moves the level","mean crop performance index")
bars(D$rho,"Spearman","C. But not the ranking","rank correlation with observed yield",
     fmt="%.3f",ylim=c(0,.78))
suptitle("Rooting depth changes the water balance a great deal and its skill not at all",
 c("Kenya short rains 2024, n = 46 counties. Only the bucket differs; dotted outline marks the shipped 1.0 m arm.",
   "WHC spans 74 to 147 mm and mean CPI spans 43 to 66 points, yet Spearman moves only 0.563 to 0.601 - a spread smaller than the uniform-vs-SoilGrids difference.",
   "No depth beats another: every paired bootstrap interval against the shipped arm crosses zero. Bias is closest to zero at 1.0 m (+0.06, against -0.28 at 0.6 m and +0.20 at 1.2 m)."))
dev.off(); cat("ok\n")
