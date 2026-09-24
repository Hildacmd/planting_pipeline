r<-read.csv("Cropyield-Data/heat_tcap_ab_results.csv",stringsAsFactors=FALSE)
OUT<-"Methodology_Testing/figs"
GRID<-"#DDD8CF"; INK<-"#2A2622"; MUT<-"#7A736A"
A<-c("t33","t30","t29"); AC<-c(t33="#8A8378",t30="#D08A2C",t29="#C1471E")
key<-function(s,g) r[r$season==s & r$group==g,][match(A,r$arm[r$season==s & r$group==g]),]
G<-list(c("KENYA LONG RAINS 2024","ALL COUNTIES","Long rains, all counties"),
        c("KENYA SHORT RAINS 2024","ALL COUNTIES","Short rains, all counties"),
        c("KENYA SHORT RAINS 2024","early (Aug-Sep)","Short rains: early (survey)"),
        c("KENYA SHORT RAINS 2024","late (Oct-Nov)","Short rains: late (survey)"),
        c("KENYA SHORT RAINS 2024","continuous","Short rains: continuous (CHIRPS)"),
        c("KENYA SHORT RAINS 2024","distinct OND","Short rains: distinct OND (CHIRPS)"))
lab<-sapply(G,`[`,3); ng<-length(G)

png(file.path(OUT,"ond_split_fig7_heat_ab.png"),1720,900,res=150)
layout(matrix(1:2,1,2),widths=c(1,1.14))
par(mar=c(5.6,13.4,5.4,1.6),oma=c(0,0,3.4,0),xpd=FALSE)

## A. is the term alive?
plot(NA,xlim=c(0,100),ylim=c(.4,ng+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(0,100,25),col=GRID,lwd=1)
for(i in 1:ng){k<-key(G[[i]][1],G[[i]][2]); y<-ng-i+1
  for(j in 1:3) rect(0,y-.34+(j-1)*.22,100*k$active[j]/k$n[j],y-.16+(j-1)*.22,col=AC[j],border=NA)
  text(101,y+.06,sprintf("n=%d",k$n[1]),adj=0,cex=.66,col=MUT,xpd=NA)}
axis(2,at=ng:1,labels=lab,las=1,col=GRID,col.axis=INK,cex.axis=.80,tck=-.012)
axis(1,at=seq(0,100,25),labels=paste0(seq(0,100,25),"%"),col=GRID,col.axis=MUT,cex.axis=.78,tck=-.02)
mtext("A. Does the heat term switch on?",3,line=1.9,adj=0,cex=1.02,font=2,col=INK)
mtext("share of counties with S_heat > 0",3,line=.7,adj=0,cex=.78,col=MUT)
legend("bottomright",inset=c(.02,-.30),horiz=TRUE,legend=c("Tcap 33 (shipped)","30","29"),
  fill=AC,border=NA,bty="n",cex=.76,text.col=INK,xpd=NA)

## B. does skill change?
par(mar=c(5.6,1.6,5.4,7.0))
xr<-range(c(r$lo,r$hi),na.rm=TRUE)*1.12
plot(NA,xlim=xr,ylim=c(.4,ng+.6),axes=FALSE,xlab="",ylab="")
abline(v=pretty(xr,5),col=GRID,lwd=1); abline(v=0,col=INK,lwd=1.4)
for(i in 1:ng){k<-key(G[[i]][1],G[[i]][2]); y<-ng-i+1
  for(j in 2:3){yy<-y+ifelse(j==2,.16,-.16)
    segments(k$lo[j],yy,k$hi[j],yy,col=AC[j],lwd=2.4)
    segments(c(k$lo[j],k$hi[j]),yy-.075,c(k$lo[j],k$hi[j]),yy+.075,col=AC[j],lwd=1.8)
    points(k$d[j],yy,pch=19,col=AC[j],cex=1.05)}}
axis(1,at=pretty(xr,5),col=GRID,col.axis=MUT,cex.axis=.76,tck=-.02)
mtext("B. Does that change skill?",3,line=1.9,adj=0,cex=1.02,font=2,col=INK)
mtext("LOO-MAE difference, Tcap 33 minus lower Tcap (t/ha)",3,line=.7,adj=0,cex=.78,col=MUT)
text(xr[2]*.98,ng+.42,"lower Tcap better ->",adj=1,cex=.70,col=MUT)
text(xr[1]*.98,ng+.42,"<- shipped better",adj=0,cex=.70,col=MUT)
par(xpd=NA)
text(xr[2]*1.06,ng/2+.5,"every interval\ncrosses zero",adj=0,cex=.78,col=INK,font=2)
mtext("S_heat threshold A/B: lowering Tcap wakes the term up but changes no score",3,
  outer=TRUE,line=1.0,adj=.015,cex=1.18,font=2,col=INK)
dev.off(); cat("ok\n")
