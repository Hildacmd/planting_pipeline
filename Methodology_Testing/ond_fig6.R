d<-readRDS("/tmp/ond_profiles.rds"); val<-d$val; P<-d$P; TX<-d$TX; TN<-d$TN
MON<-c("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
dlab<-function(x){x<-round(x);sprintf("%s-d%d",MON[(x-1)%/%3+1],(x-1)%%3+1)}
OUT<-"Methodology_Testing/figs"
C_E<-"#1B72B8"; C_L<-"#C1471E"; C_W<-"#EDE3D2"; GRID<-"#DDD8CF"; INK<-"#2A2622"; MUT<-"#7A736A"
DK<-19:36
med<-function(M,g) apply(M[g,DK,drop=FALSE],2,median,na.rm=TRUE)
qr <-function(M,g,p) apply(M[g,DK,drop=FALSE],2,quantile,p,na.rm=TRUE)

panel<-function(M,g1,g2,ylab,ttl,sub,yl=NULL,band=TRUE,hline=NULL,hlab=NULL){
  m1<-med(M,g1); m2<-med(M,g2)
  if(is.null(yl)) yl<-range(c(qr(M,g1,.25),qr(M,g1,.75),qr(M,g2,.25),qr(M,g2,.75)),na.rm=TRUE)
  yl<-yl+c(-.02,.16)*diff(yl)
  plot(NA,xlim=c(19,36),ylim=yl,axes=FALSE,xlab="",ylab="")
  rect(27.5,yl[1],33.5,yl[2],col=C_W,border=NA)
  abline(h=pretty(yl,5),col=GRID,lwd=1)
  if(band){for(gg in list(list(g1,C_E),list(g2,C_L)))
    polygon(c(DK,rev(DK)),c(qr(M,gg[[1]],.25),rev(qr(M,gg[[1]],.75))),col=paste0(gg[[2]],"22"),border=NA)}
  if(!is.null(hline)){abline(h=hline,col="#8A7A5E",lty=2,lwd=1.4)
    text(19.2,hline+diff(yl)*.030,hlab,adj=0,cex=.72,col="#8A7A5E",font=2)}
  lines(DK,m1,col=C_E,lwd=2.6); points(DK,m1,pch=19,col=C_E,cex=.6)
  lines(DK,m2,col=C_L,lwd=2.6); points(DK,m2,pch=19,col=C_L,cex=.6)
  axis(1,at=seq(19,36,3),labels=dlab(seq(19,36,3)),col=GRID,col.axis=MUT,cex.axis=.70,las=2,tck=-.025)
  axis(2,at=pretty(yl,5),las=1,col=GRID,col.axis=MUT,cex.axis=.74,tck=-.02)
  mtext(ttl,3,line=1.85,adj=0,cex=.95,font=2,col=INK)
  mtext(sub,3,line=.75,adj=0,cex=.74,col=MUT)
  mtext(ylab,2,line=3.5,cex=.78,col=MUT)
}

for(sp in c("survey","chirps")){
 if(sp=="survey"){g1<-val$survey_ond_regime=="early (Aug-Sep)"; n1<-"early (Aug-Sep)"; n2<-"late (Oct-Nov)"
   head<-"Rainfall, temperature and heat load by SURVEY-defined OND regime"}
 else {g1<-val$chirps_rain_structure=="continuous (no dry break)"; n1<-"continuous (no dry break)"; n2<-"distinct OND (dry break)"
   head<-"Rainfall, temperature and heat load by CHIRPS rainfall structure"}
 g2<-!g1
 png(file.path(OUT,sprintf("ond_split_fig6_%s.png",sp)),1760,1180,res=150)
 par(mfrow=c(2,2),mar=c(5.6,5.4,5.0,2.6),oma=c(4.6,0,5.0,0),xpd=FALSE)
 panel(P,g1,g2,"mm per dekad","A. Rainfall (CHIRPS normal 1996-2025)","median county, shaded = IQR")
 panel(TX,g1,g2,"deg C","B. Daily maximum temperature (CHIRTS normal)","dashed lines = the three S_heat Tcap arms tested",
   hline=NULL)
 for(j in 1:3){hh<-c(33,30,29)[j]
   segments(19,hh,35.05,hh,col="#8A7A5E",lty=c(2,3,4)[j],lwd=1.3)
   text(35.35,hh,hh,adj=0,cex=.70,col="#8A7A5E",font=2)}
 panel((TX+TN)/2,g1,g2,"deg C","C. Mean temperature","(Tmax + Tmin) / 2")
 GD<-pmax(pmin((TX+TN)/2,30)-10,0)*10.14
 panel(GD,g1,g2,"GDD per dekad","D. Growing degree days","Tbase 10 C, capped at 30 C")
 par(xpd=NA)
 mtext(head,3,outer=TRUE,line=2.9,adj=.02,cex=1.20,font=2,col=INK)
 mtext(sprintf("Shaded band = the OND detection window, dekads 28-33.   %s n=%d   |   %s n=%d",
   n1,sum(g1),n2,sum(g2)),3,outer=TRUE,line=1.5,adj=.02,cex=.85,col=MUT)
 par(fig=c(0,1,0,1),oma=c(0,0,0,0),mar=c(0,0,0,0),new=TRUE)
 plot(0:1,0:1,type="n",axes=FALSE,xlab="",ylab="")
 legend("bottom",horiz=TRUE,legend=c(n1,n2),col=c(C_E,C_L),lwd=2.8,bty="n",
   cex=.92,text.col=INK,seg.len=2.4,inset=c(0,.012))
 dev.off()
}
cat("ok\n")
