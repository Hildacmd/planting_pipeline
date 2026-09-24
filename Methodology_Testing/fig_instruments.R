source("Methodology_Testing/theme.R")
z<-readRDS("/tmp/gdd_val.rds"); G<-z$G; d<-z$d
INST<-list(
 list("LGP",            "can the crop grow here at all?",        "answers before the season", -35, -35, "#9C8FA8"),
 list("GDD clock",      "when will each stage occur?",           "answers at planting",         0,   0, PAL[["one"]]),
 list("Water balance",  "how much stress fell in each stage?",   "answers as each dekad closes", 0, 130, PAL[["e"]]),
 list("Vegetation index","did the canopy behave as modelled?",   "answers after the canopy responds", 45, 130, PAL[["two"]]))
FLO<-91; MAT<-140
PX("Methodology_Testing/figs/instrument_division.png",2100,880)
par(mar=c(6.6,13.4,7.4,20.0),oma=c(.4,0,3.6,.4),xpd=FALSE)
n<-length(INST)
plot(NA,xlim=c(-45,150),ylim=c(.4,n+.7),axes=FALSE,xlab="",ylab="")
rect(FLO-12,.4,FLO+12,n+.7,col="#F3E4DC",border=NA)
abline(v=seq(-40,150,20),col=GRID,lwd=1)
abline(v=0,col=INK,lwd=1.4)
for(i in 1:n){ y<-n-i+1; a<-INST[[i]]
  x0<-a[[4]]; x1<-a[[5]]; cl<-a[[6]]
  if(x1>x0) rect(x0,y-.24,x1,y+.24,col=paste0(cl,"55"),border=cl,lwd=1.6)
  else points(x0,y,pch=18,col=cl,cex=2.2)
  text(156,y+.16,a[[2]],adj=0,cex=.82,col=INK,xpd=NA)
  text(156,y-.20,a[[3]],adj=0,cex=.74,col=cl,font=3,xpd=NA)}
segments(0,n+.42,FLO,n+.42,col=PAL[["one"]],lwd=1.6)
arrows(0,n+.42,FLO,n+.42,length=.06,angle=20,col=PAL[["one"]],lwd=1.6,code=3)
text(FLO/2,n+.60,"91 d of lead time",cex=.80,col=PAL[["one"]],font=2)
text(FLO,-0.15,"flowering",cex=.80,col="#9A6B57",font=2,adj=.5,xpd=NA)
text(0,-0.15,"planting",cex=.80,col=INK,font=2,adj=.5,xpd=NA)
gridy(n:1,sapply(INST,`[[`,1),cex=.90)
gridx(seq(-40,140,20),cex=.78,line=3.0,title="days relative to planting")
suptitle("Each instrument answers a different question, and answers it at a different time",
 c("The shaded band is the flowering window. The clock reaches it 91 days ahead; a vegetation index cannot report on it until after the canopy has responded.",
   "That gap is structural, not a matter of index quality: an index measures state that has already occurred, so it cannot deliver lead time before the critical window."))
dev.off(); cat("ok\n")
