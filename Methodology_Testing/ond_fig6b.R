d<-readRDS("/tmp/ond_profiles.rds"); val<-d$val; P<-d$P; TX<-d$TX; TN<-d$TN
rd<-readRDS("/tmp/raindays.rds")
stopifnot(identical(rd$county,val$county))
MON<-c("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
dlab<-function(x){x<-round(x);sprintf("%s-d%d",MON[(x-1)%/%3+1],(x-1)%%3+1)}
OUT<-"Methodology_Testing/figs"
C_E<-"#1B72B8"; C_L<-"#C1471E"; C_W<-"#EDE3D2"; GRID<-"#DDD8CF"; INK<-"#2A2622"; MUT<-"#7A736A"
DK<-19:36
# rain-day matrices are already dk19-36; pad the 36-column ones to match
R1<-matrix(NA,nrow(val),36); R1[,DK]<-rd$rd1
R10<-matrix(NA,nrow(val),36); R10[,DK]<-rd$rd10
med<-function(M,g) apply(M[g,DK,drop=FALSE],2,median,na.rm=TRUE)
qr <-function(M,g,p) apply(M[g,DK,drop=FALSE],2,quantile,p,na.rm=TRUE)

panel<-function(M,g1,g2,ylab,ttl,sub,tcap=FALSE){
  m1<-med(M,g1); m2<-med(M,g2)
  yl<-range(c(qr(M,g1,.25),qr(M,g1,.75),qr(M,g2,.25),qr(M,g2,.75)),na.rm=TRUE)
  if(tcap) yl<-range(c(yl,28.4,33.6))
  yl<-yl+c(-.03,.14)*diff(yl)
  plot(NA,xlim=c(19,36),ylim=yl,axes=FALSE,xlab="",ylab="")
  rect(27.5,yl[1],33.5,yl[2],col=C_W,border=NA)
  abline(h=pretty(yl,5),col=GRID,lwd=1)
  for(gg in list(list(g1,C_E),list(g2,C_L)))
    polygon(c(DK,rev(DK)),c(qr(M,gg[[1]],.25),rev(qr(M,gg[[1]],.75))),col=paste0(gg[[2]],"22"),border=NA)
  if(tcap) for(j in 1:3){hh<-c(33,30,29)[j]
    segments(19,hh,35.0,hh,col="#8A7A5E",lty=c(2,3,4)[j],lwd=1.3)
    text(35.3,hh,hh,adj=0,cex=.66,col="#8A7A5E",font=2)}
  lines(DK,m1,col=C_E,lwd=2.5); points(DK,m1,pch=19,col=C_E,cex=.55)
  lines(DK,m2,col=C_L,lwd=2.5); points(DK,m2,pch=19,col=C_L,cex=.55)
  axis(1,at=seq(19,36,3),labels=dlab(seq(19,36,3)),col=GRID,col.axis=MUT,cex.axis=.64,las=2,tck=-.028)
  axis(2,at=pretty(yl,5),las=1,col=GRID,col.axis=MUT,cex.axis=.70,tck=-.022)
  mtext(ttl,3,line=1.75,adj=0,cex=.88,font=2,col=INK)
  mtext(sub,3,line=.70,adj=0,cex=.68,col=MUT)
  mtext(ylab,2,line=3.1,cex=.72,col=MUT)
}
GD<-pmax(pmin((TX+TN)/2,30)-10,0)*10.14

for(sp in c("survey","chirps")){
 if(sp=="survey"){g1<-val$survey_ond_regime=="early (Aug-Sep)"; n1<-"early (Aug-Sep)"; n2<-"late (Oct-Nov)"
   head<-"Rainfall, rain days, temperature and heat load by SURVEY-defined OND regime"
   au<-"Aug-Sep rain days: 36.3 vs 9.4 days >=1mm (p=0.007)   |   5.5 vs 0.3 days >=10mm (p=0.008)"}
 else {g1<-val$chirps_rain_structure=="continuous (no dry break)"; n1<-"continuous (no dry break)"; n2<-"distinct OND (dry break)"
   head<-"Rainfall, rain days, temperature and heat load by CHIRPS rainfall structure"
   au<-"Aug-Sep rain days: 38.2 vs 8.6 days >=1mm   |   7.5 vs 0.1 days >=10mm   (this split is DEFINED by Aug-Sep rainfall, so these are descriptive, not a test)"}
 g2<-!g1
 png(file.path(OUT,sprintf("ond_split_fig6_%s.png",sp)),2000,1220,res=150)
 par(mfrow=c(2,3),mar=c(5.4,4.8,4.8,1.6),oma=c(4.4,0,5.6,0),xpd=FALSE)
 panel(P,g1,g2,"mm per dekad","A. Rainfall total","CHIRPS normal 1996-2025; shaded = IQR")
 panel(R1,g1,g2,"days per dekad","B. Rain days (>= 1 mm)","counted from daily CHIRPS, 30 years")
 panel(R10,g1,g2,"days per dekad","C. Heavy rain days (>= 10 mm)","counted from daily CHIRPS, 30 years")
 panel(TX,g1,g2,"deg C","D. Daily maximum temperature","CHIRTS normal; dashed = S_heat Tcap arms",tcap=TRUE)
 panel((TX+TN)/2,g1,g2,"deg C","E. Mean temperature","(Tmax + Tmin) / 2")
 panel(GD,g1,g2,"GDD per dekad","F. Growing degree days","Tbase 10 C, capped at 30 C")
 par(fig=c(0,1,0,1),oma=c(0,0,0,0),mar=c(0,0,0,0),new=TRUE,xpd=NA)
 plot(0:1,0:1,type="n",axes=FALSE,xlab="",ylab="")
 mtext(head,3,line=-1.9,adj=.015,cex=1.16,font=2,col=INK)
 mtext(sprintf("Shaded band = OND detection window, dekads 28-33.   %s n=%d   |   %s n=%d",n1,sum(g1),n2,sum(g2)),
   3,line=-3.3,adj=.015,cex=.80,col=MUT)
 mtext(au,3,line=-4.5,adj=.015,cex=.78,col=INK,font=2)
 legend("bottom",horiz=TRUE,legend=c(n1,n2),col=c(C_E,C_L),lwd=2.8,bty="n",cex=.92,
   text.col=INK,seg.len=2.4,inset=c(0,.010))
 dev.off()
}
cat("ok\n")
